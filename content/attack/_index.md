---
title: "ATT&CK 覆盖"
description: "用 Wazuh 七天真实告警算出来的 ATT&CK 覆盖：总告警、带 mitre.id 的比例、未映射条数，以及战术 × 技术的命中矩阵。未映射的告警单独列出，不摊进任何技术。"
layout: "list"
data-xk-ssr: attack
---

这一页的数字全部来自 srv2 上 Wazuh 索引器里的真实告警，按 `rule.mitre.id` / `rule.mitre.tactic`
聚合；Wazuh 规则没带 `mitre.id` 的告警单独计成「未映射」，不摊进任何技术。
