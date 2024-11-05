import pandas as pd
import requests
import zipfile
import io
import yaml
from concurrent.futures import ThreadPoolExecutor
import time
import os
from datetime import datetime
pd.options.mode.copy_on_write = True
# 加载配置文件
with open("config.yaml", "r", encoding="utf-8") as file:
    config = yaml.safe_load(file)

# 创建当天日期的目录
today = datetime.now().strftime("%Y-%m-%d")
os.makedirs(today, exist_ok=True)

# 数据标准化函数
def standardize_data(df, domain_field, rank_field, source_name):
    try:
        # 统一 Domain 字段格式
        if domain_field in df.columns:
            df['Domain'] = df[domain_field].str.strip().str.lower()  # 去除空格并转换为小写
        else:
            raise KeyError(f"'{domain_field}' not found in DataFrame columns. Available columns: {df.columns.tolist()}")
        
        # 添加 Rank 字段的逻辑
        if rank_field is None:  # 如果 rank_field 为 None
            df['Rank'] = 999999  # 默认添加 Rank 字段为 999999
        else:
            if rank_field in df.columns:
                df['Rank'] = df[rank_field].astype(int)  # 确保 Rank 为整数类型
            else:
                raise KeyError(f"'{rank_field}' not found in DataFrame columns. Available columns: {df.columns.tolist()}")
    except KeyError as e:
        print(f"KeyError in {source_name}: {e} - Check if the column names are correct in the DataFrame.")
        raise  # 重新抛出异常以便外部捕获
    return df

# 下载并解压文件
def download_and_extract(source_name, url, has_header, original_fields, used_fields, domain_field, rank_field, filename, max_rows=1000000, timeout=10, retry_count=3, exclude=None):
    print(f"Downloading data from {source_name}...")
    for attempt in range(retry_count):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()

            # 处理ZIP格式
            if url.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    csv_name = z.namelist()[0]
                    with z.open(csv_name) as f:
                        df = pd.read_csv(f, header=0 if has_header else None, nrows=max_rows)
            else:
                df = pd.read_csv(io.BytesIO(response.content), header=0 if has_header else None, nrows=max_rows)

            # 如果没有表头，使用 original_fields
            if not has_header:
                df.columns = original_fields  # 使用 YAML 中定义的列名
            else:
                df.columns = original_fields

            # 打印列名以调试
            print(f"Columns in {source_name}: {df.columns.tolist()}")

            # 数据标准化
            df = standardize_data(df, domain_field, rank_field, source_name)

            # 排除特定数据项
            if exclude:
                df = df[~df[domain_field].isin(exclude)]  # 过滤掉要排除的行

            # 检查下载的数据
            print(f"Data shape after downloading from {source_name}: {df.shape}")
            print(df.head())

            # 保存数据到当天日期的目录
            df.to_csv(os.path.join(today, filename), index=False, encoding="utf-8-sig")
            return df[used_fields]  # 只返回使用的字段
        except requests.exceptions.RequestException as e:
            print(f"Network error on attempt {attempt + 1} for {source_name}: {e}")
            time.sleep(1)  # 等待一秒后重试
        except zipfile.BadZipFile as e:
            print(f"Bad ZIP file error for {source_name}: {e}")
            break  # 不重试，直接退出
        except Exception as e:
            print(f"Unexpected error on attempt {attempt + 1} for {source_name}: {e}")
            time.sleep(1)  # 等待一秒后重试

    # 如果下载失败，尝试从备份目录加载数据
    backup_file_path = os.path.join("backup", filename)
    if os.path.exists(backup_file_path):
        print(f"Using backup data from {backup_file_path}")
        df = pd.read_csv(backup_file_path, header=0 if has_header else None, nrows=max_rows)
        # 如果没有表头，使用 original_fields
        if not has_header:
            df.columns = original_fields  # 使用 YAML 中定义的列名

        df = standardize_data(df, domain_field, rank_field, source_name)

        # 排除特定数据项
        if exclude:
            df = df[~df[domain_field].isin(exclude)]  # 过滤掉要排除的行

        # 检查备份数据
        print(f"Backup data shape: {df.shape}")
        print(df.head())
        
        return df[used_fields]  # 只返回使用的字段
    else:
        print(f"No backup data found for {filename}.")
    return None

# 设置下载线程数
max_threads = 5
combined_data = []

def process_source(source_name, source_info):
    try:
        # 下载并处理源数据
        df = download_and_extract(
            source_name,
            source_info["url"],
            source_info["has_header"],
            source_info["original_fields"],
            source_info["used_fields"],
            source_info["domain_field"],
            source_info["rank_field"],
            source_info["filename"],  # 使用文件名
            max_rows=1000000,  # 只取前一百万条数据
            timeout=source_info.get("timeout", 10),
            retry_count=source_info.get("retry_count", 3),
            exclude=source_info.get("exclude", None)
        )

        if df is not None:
            # 使用 .copy() 创建 DataFrame 的副本，避免 SettingWithCopyWarning
            df = df.copy()

            # 添加源和评分
            df.loc[:, "Source"] = source_name  # 使用 .loc 进行赋值
            df.loc[:, "TrustScore"] = source_info["trust_score"]  # 使用 .loc 进行赋值
            df.loc[:, "SecurityScore"] = source_info["security_score"]  # 使用 .loc 进行赋值
            combined_data.append(df)
        else:
            print(f"Failed to process data from {source_name} after retries.")
    except Exception as e:
        print(f"Error processing source {source_name}: {e}")

# 使用线程池执行
with ThreadPoolExecutor(max_workers=max_threads) as executor:
    futures = [executor.submit(process_source, source_name, source_info) for source_name, source_info in config["sources"].items()]
    for future in futures:
        future.result()

# 合并数据
if combined_data:
    merged_df = pd.concat(combined_data, ignore_index=True)

    # 按域名聚合
    grouped_df = (
        merged_df.groupby("Domain")
        .agg({
            "Rank": "sum",  # 所有数据源的 Rank 值相加
            "Source": lambda x: ", ".join(set(x)),  # 合并来源
            "TrustScore": "sum",  # 合并信任度
            "SecurityScore": "sum"  # 合并安全度
        })
        .reset_index()
    )

    # 检查每个域名的源数量
    source_counts = merged_df.groupby("Domain")["Source"].nunique().reset_index()
    source_counts.columns = ["Domain", "SourceCount"]

    # 合并源数量到 grouped_df
    grouped_df = grouped_df.merge(source_counts, on="Domain")

    # 如果只有一个源有 Rank，则其他源的 Rank 加上 999999
    grouped_df["Rank"] = grouped_df.apply(
        lambda row: row["Rank"] + (row["SourceCount"] - 1) * 999999 if row["SourceCount"] == 1 else row["Rank"],
        axis=1
    )

    # 计算综合评分
    grouped_df["AggregateScore"] = grouped_df["TrustScore"] * 0.5 + grouped_df["SecurityScore"] * 0.5

    # 修改排名逻辑：根据 AggregateScore 降序和 Rank 升序排序
    grouped_df = grouped_df.sort_values(by=["AggregateScore", "Rank"], ascending=[False, True]).reset_index(drop=True)

    # 生成新的 Rank 列，Rank 从 1 开始
    grouped_df["Rank"] = range(1, len(grouped_df) + 1)

    # 生成白名单
    whitelist_df = grouped_df[grouped_df["AggregateScore"] > 10]  # 只保留综合评分高于5的域名
    whitelist_df = whitelist_df.sort_values(by="Rank", ascending=True).reset_index(drop=True)  # 按总排名排序

    # 保存为CSV文件
    whitelist_df.to_csv("whitelist.csv", index=False, encoding="utf-8-sig")
    print("Whitelist generated and saved to 'whitelist.csv'")
else:
    print("No data was processed successfully.")
