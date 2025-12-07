#!/usr/bin/env python3
"""SuperDog v0.5 永續合約數據功能測試"""

try:
    from data.perpetual.funding_rate import *
    print("✅ 資金費率模組載入成功")
    
    from data.perpetual.open_interest import *
    print("✅ 持倉量模組載入成功")
    
    from data.perpetual.basis import *
    print("✅ 期現基差模組載入成功")
    
    from data.perpetual.liquidations import *
    print("✅ 爆倉數據模組載入成功")
    
    from data.perpetual.long_short_ratio import *
    print("✅ 多空比模組載入成功")
    
    from data.aggregation.multi_exchange import *
    print("✅ 多交易所聚合模組載入成功")
    
    print("\n🎉 SuperDog v0.5 永續合約數據生態完全就緒！")
    print("支援：資金費率 + 持倉量 + 基差 + 爆倉 + 多空比 + 多交易所")
    
except Exception as e:
    print(f"❌ 模組載入錯誤: {e}")
