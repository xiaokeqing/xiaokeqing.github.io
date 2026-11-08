{
 "generatedAt": "2026-11-08T23:30:26+08:00",
 "windowDays": 7,
 "total": 1812272,
 "mapped": 903111,
 "unmapped": 909161,
 "mappedPct": 49.83,
 "tactics": [
  {
   "id": "TA0006",
   "name": "Credential Access",
   "count": 494435
  },
  {
   "id": "TA0043",
   "name": "Reconnaissance",
   "count": 399894
  },
  {
   "id": "TA0005",
   "name": "Defense Evasion",
   "count": 8050
  },
  {
   "id": "TA0004",
   "name": "Privilege Escalation",
   "count": 8050
  },
  {
   "id": "TA0001",
   "name": "Initial Access",
   "count": 7808
  },
  {
   "id": "TA0003",
   "name": "Persistence",
   "count": 7808
  },
  {
   "id": "TA0008",
   "name": "Lateral Movement",
   "count": 4501
  },
  {
   "id": "TA0007",
   "name": "Discovery",
   "count": 47
  },
  {
   "id": "TA0040",
   "name": "Impact",
   "count": 39
  }
 ],
 "techniques": [
  {
   "id": "T1110",
   "name": "Brute Force",
   "count": 431278,
   "tactics": [
    "TA0006"
   ],
   "cells": [
    {
     "tactic": "TA0006",
     "count": 431278,
     "alpha": 0.42
    }
   ]
  },
  {
   "id": "T1595",
   "name": "Active Scanning",
   "count": 399894,
   "tactics": [
    "TA0043"
   ],
   "cells": [
    {
     "tactic": "TA0043",
     "count": 399894,
     "alpha": 0.42
    }
   ]
  },
  {
   "id": "T1110.001",
   "name": "Password Guessing",
   "count": 63110,
   "tactics": [
    "TA0006",
    "TA0008"
   ],
   "cells": [
    {
     "tactic": "TA0006",
     "count": 63110,
     "alpha": 0.37
    },
    {
     "tactic": "TA0008",
     "count": 25,
     "alpha": 0.16
    }
   ]
  },
  {
   "id": "T1078",
   "name": "Valid Accounts",
   "count": 7808,
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
     "count": 7808,
     "alpha": 0.31
    },
    {
     "tactic": "TA0001",
     "count": 7808,
     "alpha": 0.31
    },
    {
     "tactic": "TA0003",
     "count": 7808,
     "alpha": 0.31
    },
    {
     "tactic": "TA0004",
     "count": 7808,
     "alpha": 0.31
    },
    {
     "tactic": "TA0008",
     "count": 3783,
     "alpha": 0.29
    }
   ]
  },
  {
   "id": "T1021",
   "name": "Remote Services",
   "count": 3783,
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
     "count": 3783,
     "alpha": 0.29
    },
    {
     "tactic": "TA0001",
     "count": 3783,
     "alpha": 0.29
    },
    {
     "tactic": "TA0008",
     "count": 3783,
     "alpha": 0.29
    },
    {
     "tactic": "TA0003",
     "count": 3783,
     "alpha": 0.29
    },
    {
     "tactic": "TA0004",
     "count": 3783,
     "alpha": 0.29
    }
   ]
  },
  {
   "id": "T1021.002",
   "name": "SMB/Windows Admin Shares",
   "count": 693,
   "tactics": [
    "TA0008"
   ],
   "cells": [
    {
     "tactic": "TA0008",
     "count": 693,
     "alpha": 0.25
    }
   ]
  },
  {
   "id": "T1548.003",
   "name": "Sudo and Sudo Caching",
   "count": 242,
   "tactics": [
    "TA0005",
    "TA0004"
   ],
   "cells": [
    {
     "tactic": "TA0005",
     "count": 242,
     "alpha": 0.22
    },
    {
     "tactic": "TA0004",
     "count": 242,
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
     "alpha": 0.17
    },
    {
     "tactic": "TA0007",
     "count": 47,
     "alpha": 0.17
    }
   ]
  },
  {
   "id": "T1565.001",
   "name": "Stored Data Manipulation",
   "count": 39,
   "tactics": [
    "TA0040"
   ],
   "cells": [
    {
     "tactic": "TA0040",
     "count": 39,
     "alpha": 0.17
    }
   ]
  },
  {
   "id": "T1021.004",
   "name": "SSH",
   "count": 25,
   "tactics": [
    "TA0006",
    "TA0008"
   ],
   "cells": [
    {
     "tactic": "TA0006",
     "count": 25,
     "alpha": 0.16
    },
    {
     "tactic": "TA0008",
     "count": 25,
     "alpha": 0.16
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
  "windowDays": 7,
  "total": 332655,
  "mapped": 306361,
  "unmapped": 26294,
  "mappedPct": 92.1,
  "byCategory": [
   {
    "category": "Attempted Information Leak",
    "count": 306171,
    "tactic": "TA0043",
    "tacticName": "Reconnaissance",
    "mapped": true
   },
   {
    "category": "Misc activity",
    "count": 15155,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "信息类签名（SSH 版本串/Go UA），无攻击阶段语义"
   },
   {
    "category": "Misc Attack",
    "count": 6411,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "DROP/Spamhaus/CINS 信誉名单命中，只知道来源坏"
   },
   {
    "category": "Generic Protocol Command Decode",
    "count": 2502,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "STREAM/HTTP 解析异常，是引擎观察不是攻击阶段"
   },
   {
    "category": "Potentially Bad Traffic",
    "count": 2168,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "同桶混有端口扫描与 webshell 上传，跨战术不摊派"
   },
   {
    "category": "Detection of a Network Scan",
    "count": 63,
    "tactic": "TA0043",
    "tacticName": "Reconnaissance",
    "mapped": true
   },
   {
    "category": "Attempted Administrator Privilege Gain",
    "count": 60,
    "tactic": "TA0004",
    "tacticName": "Privilege Escalation",
    "mapped": true
   },
   {
    "category": "Not Suspicious Traffic",
    "count": 56,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "签名自述非可疑，不映射"
   },
   {
    "category": "Web Application Attack",
    "count": 53,
    "tactic": "TA0001",
    "tacticName": "Initial Access",
    "mapped": true
   },
   {
    "category": "A Network Trojan was detected",
    "count": 6,
    "tactic": "TA0011",
    "tacticName": "Command and Control",
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
    "category": "",
    "count": 2,
    "tactic": "",
    "tacticName": "",
    "mapped": false,
    "why": "告警本身没有 category 字段"
   },
   {
    "category": "Attempted User Privilege Gain",
    "count": 2,
    "tactic": "TA0004",
    "tacticName": "Privilege Escalation",
    "mapped": true
   }
  ],
  "tactics": [
   {
    "id": "TA0043",
    "name": "Reconnaissance",
    "count": 306234,
    "categories": [
     {
      "category": "Attempted Information Leak",
      "count": 306171
     },
     {
      "category": "Detection of a Network Scan",
      "count": 63
     }
    ]
   },
   {
    "id": "TA0004",
    "name": "Privilege Escalation",
    "count": 62,
    "categories": [
     {
      "category": "Attempted Administrator Privilege Gain",
      "count": 60
     },
     {
      "category": "Attempted User Privilege Gain",
      "count": 2
     }
    ]
   },
   {
    "id": "TA0001",
    "name": "Initial Access",
    "count": 53,
    "categories": [
     {
      "category": "Web Application Attack",
      "count": 53
     }
    ]
   },
   {
    "id": "TA0011",
    "name": "Command and Control",
    "count": 6,
    "categories": [
     {
      "category": "A Network Trojan was detected",
      "count": 6
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
   }
  ],
  "unmappedCategories": [
   {
    "category": "Misc activity",
    "count": 15155,
    "why": "信息类签名（SSH 版本串/Go UA），无攻击阶段语义"
   },
   {
    "category": "Misc Attack",
    "count": 6411,
    "why": "DROP/Spamhaus/CINS 信誉名单命中，只知道来源坏"
   },
   {
    "category": "Generic Protocol Command Decode",
    "count": 2502,
    "why": "STREAM/HTTP 解析异常，是引擎观察不是攻击阶段"
   },
   {
    "category": "Potentially Bad Traffic",
    "count": 2168,
    "why": "同桶混有端口扫描与 webshell 上传，跨战术不摊派"
   },
   {
    "category": "Not Suspicious Traffic",
    "count": 56,
    "why": "签名自述非可疑，不映射"
   },
   {
    "category": "",
    "count": 2,
    "why": "告警本身没有 category 字段"
   }
  ],
  "observedFrom": "2026-11-05 00:00",
  "observedTo": "2026-11-08 23:30",
  "files": 4,
  "bytes": 1299979081,
  "coverage": "窗口 7 天；可读日志 4 个文件（约 1.21 GB），实际覆盖 2026-11-05 00:00 → 2026-11-08 23:30（约 4.0 天）",
  "note": "Suricata 没有 ATT&CK 字段：本块是 13 条 category 的人工对照（7 条映射到 5 个战术），表外/留空的 category 一律进未映射；与上面 Wazuh 是两套数据源，条数不可相加。",
  "source": {
   "system": "Suricata eve.json*",
   "channel": "ssh secagent-srv2 → 直读 /opt/suricata/logs/eve.json*",
   "table": "scripts/attack-coverage.py 的 SURICATA_CATEGORY_TACTIC（人工对照 13 条）"
  }
 }
}
