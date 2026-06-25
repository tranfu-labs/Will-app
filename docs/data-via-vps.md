# 数据获取:一律走东京 VPS(geo-block 节点)

> **铁律:yizhi / ArbBot 需要任何交易所真实数据(funding 费率、历史、市场快照),
> 一律在东京 VPS 上取,绝不在本机直连交易所。本机 IP 被 geo-block(api.binance.com
> 等超时);VPS 的 IP 在境外、可正常取证。**

## 为什么

- 本机直连交易所公共 API(Binance/Bybit/OKX…)大面积 RequestTimeout(geo-block)。实测仅 Gate/Coinex/Phemex 偶尔通,Binance/Bybit 等主力**本机取不到**。
- 东京 VPS(AWS ap-northeast-1)IP 正确,geo-block 已解,Binance+Bybit 等全部可取。ArbBot 的真数据证据(含"裸 taker 无 edge")都是 VPS 取的。

## VPS 连接(只读取证节点,安全)

| 项 | 值 |
|---|---|
| Host | `13.158.71.214`(东京) |
| 用户 | `ubuntu` |
| 密钥 | `~/Downloads/ArbBot.pem`(本机持有,**绝不提交**) |
| 代码 | `~/arbbot`(非 git,rsync 同步;`.venv` 有 ccxt + pydantic) |
| 性质 | **只读公共 API**:无交易密钥、不下单。取 funding 数据安全 |

```bash
ssh -i ~/Downloads/ArbBot.pem ubuntu@13.158.71.214
```

## 取数模式:fetch-on-VPS → 本机缓存 → 本机纯分析

**分离"取数(VPS、慢、联网)"和"分析/回测(本机、快、纯函数、可确定性测试)"**——这是 ArbBot `--dump`/`--prefetched` 模式,也是 yizhi 的数据层设计:

1. **取数(VPS)**:本机写脚本,管道喂 VPS 的 python 跑(脚本不留 VPS):
   ```bash
   ssh -i ~/Downloads/ArbBot.pem ubuntu@13.158.71.214 'cd ~/arbbot && .venv/bin/python -' < local_fetch.py
   ```
   或直接用 `scripts/fetch_funding_via_vps.py`(见下)。
2. **缓存(本机)**:取到的真数据写本机 `data/funding_cache.json`(两所对齐序列 + interval + 快照价差)。
3. **回测/分析(本机)**:yizhi 的回测探针**读缓存**、用 ArbBot 的纯函数 `backtest_spec` 在本机跑——**无网络、确定性、可测试**。yizhi 的回路里**永不 SSH**。

## yizhi 的数据获取工具

- `scripts/fetch_funding_via_vps.py` —— 在 VPS 取 Binance+Bybit 全市场 funding 快照、按跨所价差选长尾候选+主流基线、拉对齐历史、写 `data/funding_cache.json`。**这是 yizhi 获取真数据的唯一入口。**
- `yizhi/environments/arbbot.py` 的回测探针读该缓存做真回测(替代早期合成数据)。

## 实测验证(2026-06)

VPS 取真 Binance+Bybit 数据,经"快照→持续性→真回测"三层过滤,在 **ID** 上跑出项目首个**正面 edge 证据**(扣费后净 +865bps,过滤后 Sharpe 0.90/胜率 79%,well-calibrated);主流 BTC 确认无边(-1870bps);多数长尾快照大但持续性差=噪声。**长尾有真边、但须持续性+真回测过滤**——全部真数据,无合成。

## 切记

- **取交易所数据 → 永远 VPS。** 本机直连 = 超时,别试。
- 取数是**离线于 yizhi 回路**的预备步(像 ArbBot `--dump`);yizhi 回路只读缓存、跑纯回测。
- `ArbBot.pem` / `.env` 含密钥,绝不进仓库、绝不打印。
