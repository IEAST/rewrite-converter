# Loon Plugins

本分支由 `rewrite-converter` 自动生成，请勿直接编辑。每次同步上游 QX rewrite 后，
GitHub Actions 会重新创建整个分支。

## 使用插件

目录结构和上游保持一致，源文件扩展名 `.conf` 会转换为 `.plugin`。例如：

```text
上游：AdBlock/AmapAds.conf
本分支：AdBlock/AmapAds.plugin
```

公开仓库可以使用 raw URL 在 Loon 中导入：

```text
https://raw.githubusercontent.com/<OWNER>/<REPOSITORY>/loon/AdBlock/AmapAds.plugin
```

也可以对 raw URL 进行 URL 编码后打开：

```text
loon://import?plugin=<ENCODED_RAW_URL>
```

## 兼容性说明

- `_source.txt`：记录生成时使用的上游仓库、分支和 commit。
- `_compatibility.json`：记录不兼容规则、验证警告、人工放行状态和文件是否生成。
- 文件存在未放行的不兼容规则时，整个文件不会发布。
- 人工放行的文件会忽略已批准的不兼容规则，并在插件顶部显示 warning。

自动转换只能验证已实现的语法映射，不能替代 Loon 真机测试。
