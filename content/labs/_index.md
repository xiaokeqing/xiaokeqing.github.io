---
title: "攻防靶场"
description: "试着攻击我：把一段输入送进真实运行的检测链路（提示词注入防护 + 敏感信息扫描），返回逐组件判定、依据与动作。只做检测，不执行、不处置。"
layout: "list"
# 由 SPA 外壳渲染（layouts/baseof.html + static/js/app.js），落到「攻防靶场」视图。
# 判定结果全部来自 POST /api/playground/check，前端只负责展示，不写死任何结论。
---
