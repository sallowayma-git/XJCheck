# Findings

- 会话末尾已提交并推送 d11d0b3；当前 HEAD 一致，无 tracked 修改。最新回放 .tmp/superworks_round25_full 完整保留。
- 旧 LEGACY-CENSUS 脚本硬编码 round23，且 SW_EVIDENCE_KEYS 缺 sw_backplate_corroboration；不能直接照搬旧数字。
- P2 增加的是 row+terminal+device 佐证，不等于完整列/电气身份证明；应单独统计，不能混称原生 SW 产出。
- I/J 原配对在终态为 discard；台账 old_pair 保留修改前状态，必须以 pairs.parquet 为状态权威。
- rules.py:_high_confidence_pairs 同时考虑 confidence_bucket 和 table_mapping，不能仅改 status 后声称所有高置信审计都会退出。需真实回放才能判断降级影响。
- V1 line_groups 是 SW 抽取输入，配对来源降级不等于删除整个 V1 引擎。
