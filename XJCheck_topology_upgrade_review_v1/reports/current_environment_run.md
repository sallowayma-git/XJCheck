# 当前环境基线运行结果

- 运行项目：`10000 远动通信柜`
- 输入页数：12
- 转换状态：`{"missing_converter": 12}`
- 结果：CLI 与 findings 写出链正常结束，但当前 Linux 容器没有安装 ODA File Converter / RealDWG / LibreDWG，因此 CAD 实体表为空。
- 解释：这不是图纸识别算法的准确率结果，只是对**当前 Reader 适配层和缺失依赖降级行为**的实测。完整几何基线必须在安装 ODA 的 Windows/Linux 环境中由 `scripts/run_corpus_baseline.py` 复跑。
