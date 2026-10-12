#!/bin/bash
cd "F:/workspace/XJToolkit"
for pid in p001 p003 p022 p044 p050 p051 p071 p075; do
  rm -rf .tmp/wb_t_base .tmp/wb_t_new
  PYTHONPATH=.planning/superworks-adapter/round22_full_src python .tmp/wb_time1.py $pid .tmp/wb_t_base base 2>/dev/null | tail -1
  PYTHONPATH=.planning/superworks-adapter/round23_full_src python .tmp/wb_time1.py $pid .tmp/wb_t_new new 2>/dev/null | tail -1
done
echo TIMING_DONE
