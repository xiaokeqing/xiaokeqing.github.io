{
 "generatedAt": "2026-11-08T22:39:23+08:00",
 "windowDays": 7,
 "total": 1804148,
 "mapped": 899198,
 "unmapped": 904950,
 "mappedPct": 49.84,
 "tactics": [
  {
   "id": "TA0006",
   "name": "Credential Access",
   "count": 492516
  },
  {
   "id": "TA0043",
   "name": "Reconnaissance",
   "count": 397902
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
   "count": 4499
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
   "count": 429126,
   "tactics": [
    "TA0006"
   ],
   "cells": [
    {
     "tactic": "TA0006",
     "count": 429126,
     "alpha": 0.42
    }
   ]
  },
  {
   "id": "T1595",
   "name": "Active Scanning",
   "count": 397902,
   "tactics": [
    "TA0043"
   ],
   "cells": [
    {
     "tactic": "TA0043",
     "count": 397902,
     "alpha": 0.42
    }
   ]
  },
  {
   "id": "T1110.001",
   "name": "Password Guessing",
   "count": 63343,
   "tactics": [
    "TA0006",
    "TA0008"
   ],
   "cells": [
    {
     "tactic": "TA0006",
     "count": 63343,
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
   "count": 691,
   "tactics": [
    "TA0008"
   ],
   "cells": [
    {
     "tactic": "TA0008",
     "count": 691,
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
 }
}
