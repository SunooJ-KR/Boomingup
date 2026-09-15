#!/usr/bin/env python3
"""원천 매매·전월세 거래 원장을 batch 단위로 적재합니다.

기본값은 앞 10,000행 dry-run입니다. --commit은 전체 파일을 적재합니다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import re
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = {
    "sale": ROOT / "output/11.1.trades_sale.txt",
    "rent": ROOT / "output/11.2.trades_rent.txt",
}
SOURCE_COLUMNS = {
    "sale": (
        "aptSeq", "aptNm", "aptDong", "umdNm", "jibun", "bonbun", "bubun", "roadNm",
        "roadNmBonbun", "roadNmBubun", "buildYear", "excluUseAr", "floor", "dealYear",
        "dealMonth", "dealDay", "sggCd", "dealAmount", "cdealType", "deal_ym", "gu",
        "is_cancelled", "deal_amount_manwon",
    ),
    "rent": (
        "aptSeq", "aptNm", "umdNm", "jibun", "roadNm", "roadNmBonbun", "roadNmBubun",
        "buildYear", "excluUseAr", "floor", "dealYear", "dealMonth", "dealDay", "sggCd",
        "deposit", "monthlyRent", "deal_ym", "gu", "deposit_manwon", "monthly_rent_manwon",
        "is_jeonse",
    ),
}
TABLE_COLUMNS = {
    "sale": (
        "apt_seq", "apt_nm", "apt_dong", "umd_nm", "jibun", "bonbun", "bubun", "road_nm",
        "road_nm_bonbun", "road_nm_bubun", "build_year", "exclu_use_ar", "floor", "deal_year",
        "deal_month", "deal_day", "sgg_cd", "deal_amount", "cdeal_type", "deal_ym", "gu",
        "is_cancelled", "deal_amount_manwon",
    ),
    "rent": (
        "apt_seq", "apt_nm", "umd_nm", "jibun", "road_nm", "road_nm_bonbun", "road_nm_bubun",
        "build_year", "exclu_use_ar", "floor", "deal_year", "deal_month", "deal_day", "sgg_cd",
        "deposit", "monthly_rent", "deal_ym", "gu", "deposit_manwon", "monthly_rent_manwon",
        "is_jeonse",
    ),
}
INTEGER_COLUMNS = {"build_year", "floor", "deal_year", "deal_month", "deal_day"}
FLOAT_COLUMNS = {"exclu_use_ar"}
DECIMAL_COLUMNS = {"deal_amount_manwon", "deposit_manwon", "monthly_rent_manwon"}
BOOLEAN_COLUMNS = {"is_cancelled", "is_jeonse"}
MISSING_FIELD = object()


class _HashingReader(io.RawIOBase):
    """COPY pass에서 실제로 읽은 원천 bytes를 hash에 포함하는 읽기 전용 wrapper입니다."""

    def __init__(self, handle: Any, digest: Any) -> None:
        self.handle = handle
        self.digest = digest

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:
        data = self.handle.read(len(buffer))
        if not data:
            return 0
        self.digest.update(data)
        buffer[:len(data)] = data
        return len(data)


def _load_loader_module() -> Any:
    """점 파일명인 50.load_db.py의 URL 마스킹·.env 읽기를 재사용합니다."""
    module_path = Path(__file__).with_name("50.load_db.py")
    spec = importlib.util.spec_from_file_location("boomingup_load_db", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("50.load_db.py 모듈을 읽을 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def masked(text: str) -> str:
    return re.sub(r"(?:postgres(?:ql)?://)[^\s'\"]+", "postgresql://***", text, flags=re.I)


def _none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _strict_int(value: str | None, column: str, row_no: int) -> int | None:
    value = _none(value)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{column}: {row_no}행의 값 {value!r}을 정수로 변환할 수 없습니다.") from exc


def _strict_float(value: str | None, column: str, row_no: int) -> float | None:
    value = _none(value)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{column}: {row_no}행의 값 {value!r}을 실수로 변환할 수 없습니다.") from exc


def _strict_decimal(value: str | None, column: str, row_no: int) -> Decimal | None:
    value = _none(value)
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{column}: {row_no}행의 값 {value!r}을 numeric으로 변환할 수 없습니다.") from exc


def _strict_bool(value: str | None, column: str, row_no: int) -> bool | None:
    value = _none(value)
    if value is None:
        return None
    truth = {"true": True, "false": False, "1": True, "0": False}
    if value.lower() not in truth:
        raise ValueError(f"{column}: {row_no}행의 값 {value!r}을 boolean으로 변환할 수 없습니다.")
    return truth[value.lower()]


def validate_trade_header(fieldnames: list[str] | None, kind: str) -> None:
    actual = tuple(fieldnames or ())
    expected = SOURCE_COLUMNS[kind]
    if actual != expected:
        raise ValueError(f"{kind} 원천 헤더가 예상과 다릅니다. 예상: {', '.join(expected)}")


def _validate_trade_row(row: dict[str | None, Any], kind: str, row_no: int) -> None:
    expected = set(SOURCE_COLUMNS[kind])
    actual = set(row)
    if None in actual or actual != expected or any(row[column] is MISSING_FIELD for column in expected):
        raise ValueError(f"{kind}: {row_no}행의 field 개수가 header와 다릅니다.")


def transform_trade_row(row: dict[str | None, Any], kind: str, row_no: int) -> tuple[Any, ...]:
    """원본의 0 채움 text는 그대로 두고 명시한 숫자 컬럼만 엄격하게 변환합니다."""
    _validate_trade_row(row, kind, row_no)
    values: list[Any] = []
    for source_column, target_column in zip(SOURCE_COLUMNS[kind], TABLE_COLUMNS[kind], strict=True):
        value = row.get(source_column)
        if target_column in INTEGER_COLUMNS:
            values.append(_strict_int(value, target_column, row_no))
        elif target_column in FLOAT_COLUMNS:
            values.append(_strict_float(value, target_column, row_no))
        elif target_column in DECIMAL_COLUMNS:
            values.append(_strict_decimal(value, target_column, row_no))
        elif target_column in BOOLEAN_COLUMNS:
            values.append(_strict_bool(value, target_column, row_no))
        else:
            values.append(_none(value))
    deal_ym = values[TABLE_COLUMNS[kind].index("deal_ym")]
    if deal_ym is None or not re.fullmatch(r"\d{6}", deal_ym):
        raise ValueError(f"deal_ym: {row_no}행은 YYYYMM 6자리여야 합니다.")
    return tuple(values)


def iter_trade_records(path: Path, kind: str, limit: int | None = None, digest: Any | None = None) -> Iterator[tuple[int, tuple[Any, ...]]]:
    with path.open("rb") as raw_handle:
        binary_handle: Any = io.BufferedReader(_HashingReader(raw_handle, digest)) if digest is not None else raw_handle
        with io.TextIOWrapper(binary_handle, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t", restkey=None, restval=MISSING_FIELD)
            validate_trade_header(reader.fieldnames, kind)
            for row_no, row in enumerate(reader, start=1):
                if limit is not None and row_no > limit:
                    break
                yield row_no, transform_trade_row(row, kind, row_no)


def scan_trade_source(path: Path, kind: str) -> tuple[str, int, str, str]:
    """파일 hash, 정확한 데이터 행 수, 거래 기간을 스트리밍으로 계산합니다."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    count = 0
    period_start: str | None = None
    period_end: str | None = None
    for row_no, values in iter_trade_records(path, kind):
        deal_ym = values[TABLE_COLUMNS[kind].index("deal_ym")]
        count = row_no
        period_start = deal_ym if period_start is None else min(period_start, deal_ym)
        period_end = deal_ym if period_end is None else max(period_end, deal_ym)
    if not count or period_start is None or period_end is None:
        raise ValueError(f"{path}: 데이터 행이 없습니다.")
    return digest.hexdigest(), count, period_start, period_end


def count_required_missing(path: Path, kind: str, limit: int | None = None) -> dict[str, int]:
    """원장 조회에 필요한 최소 식별·거래일 컬럼의 빈 값을 보고합니다."""
    required = ("apt_seq", "umd_nm", "sgg_cd", "deal_ym")
    positions = {column: TABLE_COLUMNS[kind].index(column) for column in required}
    missing = {column: 0 for column in required}
    for _, values in iter_trade_records(path, kind, limit):
        for column, position in positions.items():
            if values[position] is None:
                missing[column] += 1
    return missing


def _table_exists(cursor: psycopg.Cursor[Any], table: str) -> bool:
    cursor.execute("select to_regclass(%s)", (f"app.{table}",))
    return cursor.fetchone()[0] is not None


def load_kind(connection: psycopg.Connection[Any], kind: str, commit: bool, limit: int) -> None:
    path = SOURCE_FILES[kind]
    if not path.is_file():
        raise FileNotFoundError(f"원천 파일이 없습니다: {path}")
    started = time.monotonic()
    # dry-run은 transaction context 자체가 rollback하도록 하여 부분 행이 남지 않게 합니다.
    result: tuple[int, int] | None = None
    with connection.transaction(force_rollback=not commit):
        with connection.cursor() as cursor:
            cursor.execute("set local statement_timeout = 0")
            needed = ("trade_batch", f"trade_{kind}")
            missing = [table for table in needed if not _table_exists(cursor, table)]
            if missing:
                raise RuntimeError("원장 테이블이 없습니다. data/db/001_boomingup_tables.sql을 먼저 적용하세요: " + ", ".join(missing))
            source_sha256, source_count, period_start, period_end = scan_trade_source(path, kind)
            load_limit = None if commit else limit
            expected_count = source_count if load_limit is None else min(source_count, load_limit)
            print(f"{kind}: 원천 {source_count:,}행, 적재 예정 {expected_count:,}행, 기간 {period_start}~{period_end}")
            cursor.execute(
                """insert into app.trade_batch
                   (kind, period_start, period_end, source_file, source_sha256, row_count, is_active, note)
                   values (%s, %s, %s, %s, %s, %s, false, %s) returning batch_id""",
                (kind, period_start, period_end, path.name, source_sha256, expected_count,
                 "원천 거래 원장 적재" if commit else "dry-run 거래 원장 적재"),
            )
            batch_id = int(cursor.fetchone()[0])
            columns = ("batch_id", "row_no", *TABLE_COLUMNS[kind])
            # write_row()은 기본 text COPY(탭 구분, None은 NULL)를 사용합니다.
            statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
                sql.Identifier("app", f"trade_{kind}"), sql.SQL(", ").join(map(sql.Identifier, columns))
            )
            loaded = 0
            required_positions = {
                column: TABLE_COLUMNS[kind].index(column)
                for column in ("apt_seq", "umd_nm", "sgg_cd", "deal_ym")
            }
            missing_required = {column: 0 for column in required_positions}
            copy_digest = hashlib.sha256() if commit else None
            with cursor.copy(statement) as copy:
                for row_no, values in iter_trade_records(path, kind, load_limit, copy_digest):
                    copy.write_row((batch_id, row_no, *values))
                    loaded = row_no
                    for column, position in required_positions.items():
                        if values[position] is None:
                            missing_required[column] += 1
                    if row_no % 50_000 == 0 or row_no == expected_count:
                        print(f"{kind}: 처리 중 [{row_no:,}/{expected_count:,}]")
            # 새 batch만 세야 과거 active batch가 남아도 검증이 정확합니다.
            cursor.execute(sql.SQL("select count(*) from {} where batch_id = %s").format(sql.Identifier("app", f"trade_{kind}")), (batch_id,))
            actual_count = int(cursor.fetchone()[0])
            if actual_count != expected_count or loaded != expected_count:
                raise RuntimeError(f"{kind}: 적재 행 수가 예상과 다릅니다 ({actual_count} != {expected_count}).")
            if copy_digest is not None and copy_digest.hexdigest() != source_sha256:
                raise RuntimeError(f"{kind}: COPY 중 읽은 원천 파일의 SHA-256이 최초 검사값과 다릅니다.")
            print(f"{kind}: 필수 컬럼 결측 수 " + ", ".join(f"{name}={count:,}" for name, count in missing_required.items()))
            if commit:
                cursor.execute("update app.trade_batch set is_active = false where kind = %s and is_active", (kind,))
                cursor.execute("update app.trade_batch set is_active = true where batch_id = %s", (batch_id,))
                cursor.execute("delete from app.trade_batch where kind = %s and batch_id <> %s", (kind, batch_id))
            result = (batch_id, actual_count)
    if result is None:
        raise RuntimeError(f"{kind}: 적재 결과를 확인하지 못했습니다.")
    batch_id, actual_count = result
    mode = "commit 완료" if commit else "dry-run 완료"
    suffix = "" if commit else " (rollback)"
    print(f"{kind}: {mode}, batch_id={batch_id:,}, {actual_count:,}행, {time.monotonic() - started:.1f}초{suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("sale", "rent", "all"), default="all")
    parser.add_argument("--database-url-env", default="DATABASE_LOADER_URL")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--limit", type=int, default=10_000, help="dry-run에서만 앞 N행을 적재합니다.")
    parser.add_argument("--validate-only", action="store_true", help="DB에 접속하지 않고 원천 파일 전체를 검증합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit <= 0:
        print("오류: --limit은 1 이상이어야 합니다.", file=sys.stderr)
        return 2
    try:
        if args.validate_only and args.commit:
            raise ValueError("--validate-only와 --commit은 함께 사용할 수 없습니다.")
        if args.validate_only:
            for kind in (("sale", "rent") if args.kind == "all" else (args.kind,)):
                source_sha256, source_count, period_start, period_end = scan_trade_source(SOURCE_FILES[kind], kind)
                missing = count_required_missing(SOURCE_FILES[kind], kind)
                print(f"{kind}: validate-only 완료, 원천 {source_count:,}행, 기간 {period_start}~{period_end}")
                print(f"{kind}: 필수 컬럼 결측 수 " + ", ".join(f"{name}={count:,}" for name, count in missing.items()))
            return 0
        loader = _load_loader_module()
        with psycopg.connect(loader.database_url(args.database_url_env)) as connection:
            for kind in (("sale", "rent") if args.kind == "all" else (args.kind,)):
                try:
                    load_kind(connection, kind, args.commit, args.limit)
                except Exception:
                    # kind 단위 transaction 실패 후에는 연결을 재사용하지 않습니다.
                    raise
    except Exception as exc:
        print(f"오류: {masked(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
