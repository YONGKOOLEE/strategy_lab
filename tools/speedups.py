"""전략실 실행 가속 — 운영 백테스트 엔진의 순수 함수 결과를 메모리에 기억(캐시)한다. 운영 저장소에는 아무것도 쓰지 않는다.

근거(2026-10-16 프로파일, 3개월 실행 312초): 시간의 약 98%가 엔진 스냅숏(store.snapshot)이고, 그중 달력 조회
KrxCalendar.session이 1,900만 회 호출·누적 159초. session(day)은 백테스트에서 같은 날짜에 같은 답을 준다:
- 달력 내용(_years)은 생성 때 정해지고 바뀌지 않는다(extend_calendar도 새 객체를 만든다).
- conflicts는 실시간 장운영 교차 확인(observe_live)에서만 늘어난다 — 비어 있지 않으면 캐시를 쓰지 않는다.
- 반환값 SessionInfo는 frozen dataclass.
daily_bar_final_at(day, calendar)도 같은 이유로 순수하다. 캐시 키에 해당 연도 달력 객체 id를 넣어, 달력이 바뀌면 다시 계산한다.
결과가 같은지는 같은 입력을 캐시 없이(--no-fast) 돌린 결과와 trades·equity 파일 비교로 확인한다(worklog 2026-10-16).
"""

from __future__ import annotations

_MISS = object()
_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    from trading_system.marketdata import calendar as cal_mod
    from trading_system.marketdata import store

    orig_session = cal_mod.KrxCalendar.session

    def session(self, trade_date):  # type: ignore[no-untyped-def]
        if self.conflicts:
            return orig_session(self, trade_date)
        cache = self.__dict__.setdefault("_lab_session_cache", {})
        key = (trade_date, id(self._years.get(trade_date.year)))  # noqa: SLF001
        hit = cache.get(key, _MISS)
        if hit is _MISS:
            hit = cache[key] = orig_session(self, trade_date)
        return hit

    cal_mod.KrxCalendar.session = session  # type: ignore[method-assign]

    orig_final = store.daily_bar_final_at
    final_cache: dict = {}

    def daily_bar_final_at(day, calendar):  # type: ignore[no-untyped-def]
        if calendar is not None and calendar.conflicts:
            return orig_final(day, calendar)
        key = (day, id(calendar), id(calendar._years.get(day.year)) if calendar is not None else None)  # noqa: SLF001
        hit = final_cache.get(key, _MISS)
        if hit is _MISS:
            hit = final_cache[key] = orig_final(day, calendar)
        return hit

    store.daily_bar_final_at = daily_bar_final_at  # store 안의 호출도 모듈 전역 이름으로 찾으므로 함께 바뀐다
    _installed = True


# --- 2단계: 증분 스냅숏 (2026-10-17) --------------------------------------------------------------
# 운영 MarketDataStore.snapshot은 판정마다 종목별로 ① 원시 봉 전체를 훑어 "판정 시각까지 확정된 봉"을 거르고
# ② 그 전체를 preprocess_daily로 다시 검사한다 → 기간·종목 수에 대해 제곱으로 느려진다.
# 같은 결과를 증분으로 낸다:
#  ① daily_bar_available(day, as_of)는 날짜에 대해 단조(확정 시각 = 그날 20:00 이후 → 날짜 순) → 정렬된 원시 봉에서 이분 탐색.
#  ② preprocess_daily의 검사는 행 단위(형식·0 이하·고저 모순)와 인접 쌍(중복·급변·사이 빠진 거래일)·행이 거래일인지(2행 이상일 때)뿐
#     → 정렬된 전체 봉에서 "처음 실패하는 접두 길이" bad_len을 한 번 계산하면, 접두 길이 m의 ok = (m < bad_len).
#  snapshot이 쓰는 것은 prepared.bars와 report.ok뿐이다. 원시 봉이 날짜순이 아니거나 예외면 그 종목은 원래 경로로 계산.
# 운영 원본 함수의 소스 지문이 아래와 다르면(운영 코드 변경) 이 단계는 설치하지 않는다 — 재검증 뒤 지문을 갱신한다.
_FINGERPRINTS = {
    "MarketDataStore.snapshot": "067157241677c016",
    "preprocess_daily": "b159917315062ab8",
    "MarketDataStore._trading_days": "9b9851e1824c2617",
    "daily_bar_available": "edec8c96c60e6a7a",
    "latest_complete_day": "3e14a78d47a0900b",
}
_snapshot_installed = False
STATS = {"fast": 0, "fallback": 0}


def _fp(fn) -> str:  # type: ignore[no-untyped-def]
    import hashlib
    import inspect
    return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()[:16]


def _bad_len(rows, is_trading, max_move):  # type: ignore[no-untyped-def]
    """정렬된 행에서 preprocess_daily가 처음 실패하는 접두 길이(전부 통과면 len+1)."""
    from decimal import Decimal
    n = len(rows)
    bad = n + 1
    for k, r in enumerate(rows):
        vals = (r.open, r.high, r.low, r.close, r.volume)
        if (any(not isinstance(v, Decimal) or not v.is_finite() for v in vals)
                or min(r.open, r.high, r.low, r.close) <= 0 or r.volume < 0
                or not (r.low <= min(r.open, r.close) and max(r.open, r.close) <= r.high)):
            return min(bad, k + 1)
        if not is_trading(r.day):                         # 휴장일 봉: 2행 이상 접두부터 실패
            bad = min(bad, max(k + 1, 2))
        if k:
            p = rows[k - 1]
            if r.day == p.day:
                return min(bad, k + 1)
            if p.close > 0 and not r.corporate_action and abs(r.close - p.close) / p.close > max_move:
                return min(bad, k + 1)
            from datetime import timedelta
            d = p.day + timedelta(days=1)
            while d < r.day:                              # 사이에 빠진 거래일
                if is_trading(d):
                    return min(bad, k + 1)
                d += timedelta(days=1)
        if bad <= k + 1:
            return bad
    return bad


def install_snapshot() -> bool:
    """증분 스냅숏 설치. 지문이 다르면 설치하지 않고 False."""
    global _snapshot_installed
    if _snapshot_installed:
        return True
    from bisect import bisect_right
    from dataclasses import replace

    from trading_system.marketdata import quality, store
    from trading_system.domain.strategy import Bar, EvaluationSnapshot, InstrumentView

    cur = {"MarketDataStore.snapshot": _fp(store.MarketDataStore.snapshot), "preprocess_daily": _fp(quality.preprocess_daily),
           "MarketDataStore._trading_days": _fp(store.MarketDataStore._trading_days),  # noqa: SLF001
           "daily_bar_available": _fp(store.daily_bar_available), "latest_complete_day": _fp(store.latest_complete_day)}
    if cur != _FINGERPRINTS:
        print(f"[speedups] 운영 코드 지문 불일치 — 증분 스냅숏 미설치(원래 경로). {cur}")
        return False

    def _state(self, inst):  # type: ignore[no-untyped-def]
        cache = self.__dict__.setdefault("_lab_snap", {})
        st = cache.get(id(inst))
        if st is not None and st["raw"] is inst.raw:
            return st
        raw = inst.raw
        days = [r.day for r in raw]
        if any(days[k] > days[k + 1] for k in range(len(days) - 1)):
            st = {"raw": raw, "ok": False}
        else:
            is_trading = lambda d: bool(self.calendar.is_trading_day(d)) if self.calendar is not None else d.weekday() < 5  # noqa: E731
            if self.calendar is None:
                st = {"raw": raw, "ok": False}            # 달력 없음: 원래 경로(_trading_days가 calendar를 씀)
            else:
                st = {"raw": raw, "ok": True, "days": days,
                      "bars": [Bar(r.day, r.open, r.high, r.low, r.close, r.volume) for r in raw],
                      "bad_len": _bad_len(raw, is_trading, quality.DEFAULT_MAX_DAILY_MOVE)}
        cache[id(inst)] = st
        return st

    def snapshot(self, evaluation_id, market, account, as_of, base_amount, instruments, positions, pending,  # type: ignore[no-untyped-def]
                 next_evaluation_at=None, history=None, recent_days=store.RECENT_ENTRY_DAYS, listed_at=None,
                 investor_flows=None):
        views = []
        cal = self.calendar.is_trading_day if self.calendar is not None else None
        lcd = store.latest_complete_day(as_of, self.calendar)
        for i in instruments:
            inst = self._data.get(i)
            pos = positions(i)
            extra: dict = {}
            flows_ok = True
            if listed_at is not None:
                extra["listed_at"] = listed_at(i)
            if investor_flows is not None:
                extra["investor_flows"], flows_ok = investor_flows(i)
            if history is not None:
                h = store.history_view(history(i), as_of, cal, recent_days)
                if pos is not None and h.holding_days is not None:
                    pos = replace(pos, holding_days=h.holding_days)
                extra.update({"last_exit_at": h.last_exit_at, "last_exit_reason": h.last_exit_reason,
                              "entries_recent": h.entries_recent})
            if inst is None or inst.raw is None:
                views.append(InstrumentView(instrument=i, data_ok=False, position=pos,
                                            has_pending_order=pending(i), **extra))
                continue
            st = _state(self, inst)
            if st["ok"]:
                days = st["days"]
                lo, hi = 0, len(days)                     # 확정된 봉 수 m: daily_bar_available가 참인 접두 길이
                while lo < hi:
                    mid = (lo + hi) // 2
                    if store.daily_bar_available(days[mid], as_of, self.calendar):
                        lo = mid + 1
                    else:
                        hi = mid
                m = lo
                bars = tuple(st["bars"][:m])
                ok = m < st["bad_len"]
                STATS["fast"] += 1
            else:
                known = [r for r in inst.raw if store.daily_bar_available(r.day, as_of, self.calendar)]
                prepared = store.preprocess_daily(known, self._trading_days, data_version=inst.data_version)  # noqa: SLF001
                bars, ok = prepared.bars, prepared.report.ok
                STATS["fallback"] += 1
            q = inst.quote
            views.append(InstrumentView(
                instrument=i, daily_bars=bars,
                last_price=q.price if q is not None and q.at <= as_of else None,
                statuses=inst.statuses or frozenset(), position=pos, has_pending_order=pending(i), **extra,
                data_ok=ok and bool(bars) and bars[-1].at >= lcd and flows_ok))
        return EvaluationSnapshot(evaluation_id, market, account, as_of, base_amount, tuple(views),
                                  next_evaluation_at)

    store.MarketDataStore.snapshot = snapshot  # type: ignore[method-assign]
    _snapshot_installed = True
    return True
