# 数据下载与标准化程序

## 概述

该程序旨在从多个数据源下载网站排名数据，并对其进行标准化处理。程序会将下载的数据合并，并生成一个包含综合评分的白名单。白名单将根据各个域名的信任度和安全度进行排序，并保存为 CSV 文件。

## 程序逻辑

1. **加载配置文件**: 程序首先加载 `config.yaml` 配置文件，该文件包含各个数据源的相关信息。

2. **创建目录**: 程序会根据当前日期创建一个目录，以便存储下载的数据文件。

3. **下载数据**: 
   - 使用多线程下载数据，支持从 ZIP 文件中提取 CSV 文件。
   - 根据配置文件中的设置，决定是否使用原始字段名。

4. **数据标准化**:
   - 对每个数据源下载的数据进行标准化处理，包括统一域名格式和处理排名字段。
   - 如果 `rank_field` 为 `null`，则默认将 `Rank` 字段设置为 `999999`。

5. **合并数据**:
   - 将所有数据源的数据合并，并按域名进行聚合。
   - 计算每个域名的总排名、信任度和安全度。

6. **生成白名单**:
   - 根据综合评分（信任度和安全度的加权平均）生成白名单。
   - 只保留综合评分高于 5 的域名，并按总排名排序。

7. **保存结果**: 将生成的白名单保存为 `whitelist.csv` 文件。

## config.yaml 配置逻辑

`config.yaml` 文件用于配置各个数据源的信息。每个数据源的配置包括以下字段：

- **url**: 数据源的下载链接。
- **has_header**: 指示 CSV 文件是否包含表头（`true` 或 `false`）。
- **original_fields**: 原始字段名列表，用于在没有表头时重命名列。
- **used_fields**: 需要在最终结果中保留的字段。
- **domain_field**: 用于标识域名的字段名。
- **rank_field**: 用于标识排名的字段名。如果为 `null`，则默认将 `Rank` 字段设置为 `999999`。
- **trust_score**: 数据源的信任度评分。
- **security_score**: 数据源的安全度评分。
- **filename**: 下载后保存的文件名。

### 示例配置

```yaml
sources:
  alexa:
    url: "https://s3.amazonaws.com/alexa-static/top-1m.csv.zip"
    has_header: false
    original_fields: ["Rank", "Domain"]
    used_fields: ["Rank", "Domain"]
    domain_field: "Domain"
    rank_field: "Rank"
    trust_score: 5
    security_score: 5
    filename: "Alexa-top-1m.csv"
```

在上述示例中，`alexa` 数据源的配置指定了下载链接、字段信息、评分等。程序将根据这些配置下载并处理数据。

## 运行程序

确保安装了所需的 Python 库（如 `pandas`, `requests`, `pyyaml` 等），然后运行主程序文件 `check_top1m.py`。程序将自动下载数据并生成白名单。

## 注意事项

- 确保网络连接正常，以便能够成功下载数据。
- 检查 `config.yaml` 中的配置是否正确，以避免下载错误。

