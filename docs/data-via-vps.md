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

## Will 的数据获取工具

- `scripts/fetch_funding_via_vps.py` —— 在 VPS 取 Binance+Bybit 全市场 funding 快照、按跨所价差选长尾候选+主流基线、拉对齐历史、写 `data/funding_cache.json`。**这是 yizhi 获取真数据的唯一入口。**
- `yizhi/environments/arbbot.py` 的回测探针读该缓存做真回测(替代早期合成数据)。

## 实测验证(2026-06)

VPS 取真 Binance+Bybit 数据,经"快照→持续性→真回测"三层过滤,在 **ID** 上跑出项目首个**正面 edge 证据**(扣费后净 +865bps,过滤后 Sharpe 0.90/胜率 79%,well-calibrated);主流 BTC 确认无边(-1870bps);多数长尾快照大但持续性差=噪声。**长尾有真边、但须持续性+真回测过滤**——全部真数据,无合成。

## 更新(2026-06,确定性裁决 + 深度取数后)

> **⚠️ 上面"ID +865bps 首个正边"是确定性 judge 建成前的人工解读,过度乐观。** `engine/judgment.py` 用固定规则判(样本量门 `n_entered≥20` 先行→否则 INSUFFICIENT;扣费净≤0→KILL;净>0且持续/Sharpe 达标→PROMOTE)。用 `YIZHI_FETCH_HIST_LIMIT=500 N_LONGTAIL=24` 取了更深更广数据后全扫:**12 KILL(enter-all 扣费净全负)+ 36 INSUFFICIENT(过滤后样本 <20)= 0 PROMOTE / 0 ITERATE**——在可得数据上**没有可确认的长尾边**。
>
> **硬约束(关键):交易所 funding 历史 API 只给 ~1 个月(~98 个 8h 周期),`HIST_LIMIT=500` 顶不上去。** 过滤到高质量窗口后必然剩个位数~十几个,judge 如实判 INSUFFICIENT。**绑定约束已从 agent/环境/判断移到「数据可得性」**:要确认长尾边,需更长历史(此 API 给不了)或换数据源(归档/付费 funding 数据)。论点"边在长尾"**未证实也未证伪**——judge 诚实地说"enter-all 亏、过滤后判不了"。

## 切记

- **取交易所数据 → 永远 VPS。** 本机直连 = 超时,别试。
- 取数是**离线于 yizhi 回路**的预备步(像 ArbBot `--dump`);yizhi 回路只读缓存、跑纯回测。
- `ArbBot.pem` / `.env` 含密钥,绝不进仓库、绝不打印。
