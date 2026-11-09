---
title: "自研检测规则 · Suricata + Wazuh"
description: "这个站自己写的检测规则：共 16 条（Suricata 7 / Wazuh 9），每条钉住证据与验证记录；本页只展示 sid、名称、检测对象、严重度与 ATT&CK 标注，不贴匹配内容原文。"
---
<!--
  本页由 layouts/detections/list.html 渲染，数据来自 data/detections.json。
  data/detections.json 由 scripts/detections-catalog.py 在构建期从
  detections/suricata/xk-lab.rules、detections/suricata/threshold.conf、
  detections/wazuh/xk-lab_rules.xml、detections/wazuh/cowrie_rules.xml 解析生成。

  改数字只改规则文件，然后重跑：
      python scripts/detections-catalog.py
  不要手改 data/detections.json，也不要在模板里写死条数。

  脱敏：脚本对所有对外字符串统一掩码 IPv4 字面量（-> x.x.x.x）与口令类赋值（-> [口令已隐藏]）；
  页面不展示 content / pcre / pattern 等匹配内容原文。
-->
