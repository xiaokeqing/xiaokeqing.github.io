{
 "generatedAt": "2026-11-09T13:01:51+08:00",
 "windowDays": 5,
 "total": 1512896,
 "mapped": 745839,
 "unmapped": 767057,
 "mappedPct": 49.3,
 "tactics": [
  {
   "id": "TA0006",
   "name": "Credential Access",
   "count": 399007
  },
  {
   "id": "TA0043",
   "name": "Reconnaissance",
   "count": 340182
  },
  {
   "id": "TA0005",
   "name": "Defense Evasion",
   "count": 6148
  },
  {
   "id": "TA0004",
   "name": "Privilege Escalation",
   "count": 6148
  },
  {
   "id": "TA0001",
   "name": "Initial Access",
   "count": 5891
  },
  {
   "id": "TA0003",
   "name": "Persistence",
   "count": 5891
  },
  {
   "id": "TA0008",
   "name": "Lateral Movement",
   "count": 3308
  },
  {
   "id": "TA0007",
   "name": "Discovery",
   "count": 47
  },
  {
   "id": "TA0040",
   "name": "Impact",
   "count": 29
  }
 ],
 "techniques": [
  {
   "id": "T1110",
   "name": "Brute Force",
   "count": 360497,
   "tactics": [
    "TA0006"
   ],
   "cells": [
    {
     "tactic": "TA0006",
     "count": 360497,
     "alpha": 0.42
    }
   ]
  },
  {
   "id": "T1595",
   "name": "Active Scanning",
   "count": 340182,
   "tactics": [
    "TA0043"
   ],
   "cells": [
    {
     "tactic": "TA0043",
     "count": 340182,
     "alpha": 0.42
    }
   ]
  },
  {
   "id": "T1110.001",
   "name": "Password Guessing",
   "count": 38463,
   "tactics": [
    "TA0006",
    "TA0008"
   ],
   "cells": [
    {
     "tactic": "TA0006",
     "count": 38463,
     "alpha": 0.36
    },
    {
     "tactic": "TA0008",
     "count": 18,
     "alpha": 0.15
    }
   ]
  },
  {
   "id": "T1078",
   "name": "Valid Accounts",
   "count": 5891,
   "tactics": [
    "TA0005",
    "TA0001",
    "TA0003",
    "TA0004",
    "TA0008"
   ],
   "cells": [
    {
     "tactic": "TA0005",
     "count": 5891,
     "alpha": 0.31
    },
    {
     "tactic": "TA0001",
     "count": 5891,
     "alpha": 0.31
    },
    {
     "tactic": "TA0003",
     "count": 5891,
     "alpha": 0.31
    },
    {
     "tactic": "TA0004",
     "count": 5891,
     "alpha": 0.31
    },
    {
     "tactic": "TA0008",
     "count": 2817,
     "alpha": 0.29
    }
   ]
  },
  {
   "id": "T1021",
   "name": "Remote Services",
   "count": 2817,
   "tactics": [
    "TA0005",
    "TA0001",
    "TA0008",
    "TA0003",
    "TA0004"
   ],
   "cells": [
    {
     "tactic": "TA0005",
     "count": 2817,
     "alpha": 0.29
    },
    {
     "tactic": "TA0001",
     "count": 2817,
     "alpha": 0.29
    },
    {
     "tactic": "TA0008",
     "count": 2817,
     "alpha": 0.29
    },
    {
     "tactic": "TA0003",
     "count": 2817,
     "alpha": 0.29
    },
    {
     "tactic": "TA0004",
     "count": 2817,
     "alpha": 0.29
    }
   ]
  },
  {
   "id": "T1021.002",
   "name": "SMB/Windows Admin Shares",
   "count": 473,
   "tactics": [
    "TA0008"
   ],
   "cells": [
    {
     "tactic": "TA0008",
     "count": 473,
     "alpha": 0.24
    }
   ]
  },
  {
   "id": "T1548.003",
   "name": "Sudo and Sudo Caching",
   "count": 257,
   "tactics": [
    "TA0005",
    "TA0004"
   ],
   "cells": [
    {
     "tactic": "TA0005",
     "count": 257,
     "alpha": 0.22
    },
    {
     "tactic": "TA0004",
     "count": 257,
     "alpha": 0.22
    }
   ]
  },
  {
   "id": "T1040",
   "name": "Network Sniffing",
   "count": 47,
   "tactics": [
    "TA0006",
    "TA0007"
   ],
   "cells": [
    {
     "tactic": "TA0006",
     "count": 47,
     "alpha": 0.18
    },
    {
     "tactic": "TA0007",
     "count": 47,
     "alpha": 0.18
    }
   ]
  },
  {
   "id": "T1565.001",
   "name": "Stored Data Manipulation",
   "count": 29,
   "tactics": [
    "TA0040"
   ],
   "cells": [
    {
     "tactic": "TA0040",
     "count": 29,
     "alpha": 0.16
    }
   ]
  },
  {
   "id": "T1021.004",
   "name": "SSH",
   "count": 18,
   "tactics": [
    "TA0006",
    "TA0008"
   ],
   "cells": [
    {
     "tactic": "TA0006",
     "count": 18,
     "alpha": 0.15
    },
    {
     "tactic": "TA0008",
     "count": 18,
     "alpha": 0.15
    }
   ]
  }
 ],
 "source": {
  "system": "Wazuh wazuh-alerts-*",
  "channel": "ssh secagent-srv2 → docker exec wazuh.indexer → curl https://[indexer]:9200",
  "note": "Wazuh 规则未带 mitre.id 的告警计入 unmapped，不计入任何技术。"
 },
 "suricata": {
  "available": true,
  "reason": "",
  "windowDays": 5,
  "total": 308378,
  "mapped": 284077,
  "unmapped": 24301,
  "mappedPct": 92.12,
  "byCategory": [
   {
    "category": "Attempted Information Leak",
    "count": 283912,
    "tactic": "TA0043",
    "tacticName": "Reconnaissance",
    "mapped": true
   },
   {
    "category": "Misc activity",
    "count": 13498,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "信息类签名（SSH 版本串/Go UA），无攻击阶段语义"
   },
   {
    "category": "Misc Attack",
    "count": 5424,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "DROP/Spamhaus/CINS 信誉名单命中，只知道来源坏"
   },
   {
    "category": "Potentially Bad Traffic",
    "count": 2963,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "同桶混有端口扫描与 webshell 上传，跨战术不摊派"
   },
   {
    "category": "Generic Protocol Command Decode",
    "count": 2364,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "STREAM/HTTP 解析异常，是引擎观察不是攻击阶段"
   },
   {
    "category": "Attempted Administrator Privilege Gain",
    "count": 54,
    "tactic": "TA0004",
    "tacticName": "Privilege Escalation",
    "mapped": true
   },
   {
    "category": "Detection of a Network Scan",
    "count": 52,
    "tactic": "TA0043",
    "tacticName": "Reconnaissance",
    "mapped": true
   },
   {
    "category": "Not Suspicious Traffic",
    "count": 51,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "签名自述非可疑，不映射"
   },
   {
    "category": "Web Application Attack",
    "count": 49,
    "tactic": "TA0001",
    "tacticName": "Initial Access",
    "mapped": true
   },
   {
    "category": "Information Leak",
    "count": 6,
    "tactic": "TA0007",
    "tacticName": "Discovery",
    "mapped": true
   },
   {
    "category": "A Network Trojan was detected",
    "count": 3,
    "tactic": "TA0011",
    "tacticName": "Command and Control",
    "mapped": true
   },
   {
    "category": "",
    "count": 1,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "告警本身没有 category 字段"
   },
   {
    "category": "Attempted User Privilege Gain",
    "count": 1,
    "tactic": "TA0004",
    "tacticName": "Privilege Escalation",
    "mapped": true
   }
  ],
  "tactics": [
   {
    "id": "TA0043",
    "name": "Reconnaissance",
    "count": 283964,
    "categories": [
     {
      "category": "Attempted Information Leak",
      "count": 283912
     },
     {
      "category": "Detection of a Network Scan",
      "count": 52
     }
    ]
   },
   {
    "id": "TA0004",
    "name": "Privilege Escalation",
    "count": 55,
    "categories": [
     {
      "category": "Attempted Administrator Privilege Gain",
      "count": 54
     },
     {
      "category": "Attempted User Privilege Gain",
      "count": 1
     }
    ]
   },
   {
    "id": "TA0001",
    "name": "Initial Access",
    "count": 49,
    "categories": [
     {
      "category": "Web Application Attack",
      "count": 49
     }
    ]
   },
   {
    "id": "TA0007",
    "name": "Discovery",
    "count": 6,
    "categories": [
     {
      "category": "Information Leak",
      "count": 6
     }
    ]
   },
   {
    "id": "TA0011",
    "name": "Command and Control",
    "count": 3,
    "categories": [
     {
      "category": "A Network Trojan was detected",
      "count": 3
     }
    ]
   }
  ],
  "unmappedCategories": [
   {
    "category": "Misc activity",
    "count": 13498,
    "why": "信息类签名（SSH 版本串/Go UA），无攻击阶段语义"
   },
   {
    "category": "Misc Attack",
    "count": 5424,
    "why": "DROP/Spamhaus/CINS 信誉名单命中，只知道来源坏"
   },
   {
    "category": "Potentially Bad Traffic",
    "count": 2963,
    "why": "同桶混有端口扫描与 webshell 上传，跨战术不摊派"
   },
   {
    "category": "Generic Protocol Command Decode",
    "count": 2364,
    "why": "STREAM/HTTP 解析异常，是引擎观察不是攻击阶段"
   },
   {
    "category": "Not Suspicious Traffic",
    "count": 51,
    "why": "签名自述非可疑，不映射"
   },
   {
    "category": "",
    "count": 1,
    "why": "告警本身没有 category 字段"
   }
  ],
  "observedFrom": "2026-11-06 00:00",
  "observedTo": "2026-11-09 13:01",
  "files": 4,
  "bytes": 1179732678,
  "coverage": "窗口 5 天；可读日志 4 个文件（约 1.10 GB），实际覆盖 2026-11-06 00:00 → 2026-11-09 13:01（约 3.5 天）",
  "note": "Suricata 没有 ATT&CK 字段：本块是 13 条 category 的人工对照（7 条映射到 5 个战术），表外/留空的 category 一律进未映射；与上面 Wazuh 是两套数据源，条数不可相加。",
  "source": {
   "system": "Suricata eve.json*",
   "channel": "ssh secagent-srv2 → 直读 /opt/suricata/logs/eve.json*",
   "table": "scripts/attack-coverage.py 的 SURICATA_CATEGORY_TACTIC（人工对照 13 条）"
  }
 }
}
