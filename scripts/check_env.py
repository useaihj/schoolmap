"""
schoolmap 개발 환경 진단 스크립트.

확인 항목:
  1. Python 패키지 (openpyxl)
  2. Node.js / npx (deploy.sh가 wrangler를 호출하기 위해 필요)
  3. CLOUDFLARE_API_TOKEN (Windows 사용자 환경변수 또는 현재 셸 환경변수)
  4. 필수 엑셀 파일 7개 존재 여부
  5. 엑셀 파일 잠금 (~$) 여부 — 잠긴 파일은 스크립트 쓰기 작업 시 실패 원인

사용 예:
  python scripts/check_env.py

종료 코드:
  0: 모든 필수 항목 통과
  1: 1개 이상의 필수 항목 실패
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
XLSX_DIR = BASE / "data" / "xlsx"

REQUIRED_EXCELS = [
    "초등학교현황.xlsx",
    "중학교현황.xlsx",
    "고등학교현황.xlsx",
    "특수학교현황.xlsx",
    "각종학교현황.xlsx",
    "울산학교주소위도경도.xlsx",
    "울산학교개교일우편번호전화번호팩스번호홈페이지.xlsx",
]

OK = "[OK]"
WARN = "[!!]"
FAIL = "[X ]"


def check_openpyxl():
    try:
        import openpyxl  # noqa: F401
        import openpyxl.workbook
        return True, f"openpyxl {openpyxl.__version__}"
    except Exception as e:
        return False, f"openpyxl 미설치: pip install openpyxl ({e})"


def check_node():
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return False, "npx 없음. Node.js 설치 필요 (https://nodejs.org)"
    try:
        r = subprocess.run([npx, "--version"], capture_output=True, text=True, timeout=10)
        return True, f"npx {r.stdout.strip()}"
    except Exception as e:
        return False, f"npx 실행 실패: {e}"


def check_cloudflare_token():
    # 현재 셸
    shell_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if shell_token:
        return True, f"현재 셸에 등록됨 (길이 {len(shell_token)})"

    # Windows 사용자 환경변수
    if sys.platform == "win32":
        try:
            r = subprocess.run(
                [
                    "powershell.exe",
                    "-Command",
                    "[Environment]::GetEnvironmentVariable('CLOUDFLARE_API_TOKEN','User')",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            val = (r.stdout or "").strip()
            if val:
                return True, (
                    f"Windows 사용자 환경변수에 등록됨 (길이 {len(val)}). "
                    f"deploy.sh 실행 시 bash에 주입 필요: "
                    f"export CLOUDFLARE_API_TOKEN=$(powershell.exe -Command "
                    f"\"[Environment]::GetEnvironmentVariable('CLOUDFLARE_API_TOKEN','User')\" | tr -d '\\r\\n')"
                )
        except Exception as e:
            return False, f"Windows 환경변수 조회 실패: {e}"

    return False, (
        "토큰 없음. https://dash.cloudflare.com/profile/api-tokens 에서 "
        "'Edit Cloudflare Workers' 템플릿으로 발급 후 Windows 사용자 환경변수 "
        "CLOUDFLARE_API_TOKEN 에 등록하세요."
    )


def check_excels():
    missing = []
    for f in REQUIRED_EXCELS:
        if not (XLSX_DIR / f).exists():
            missing.append(f)
    if missing:
        return False, f"누락 {len(missing)}개: {missing} (위치: {XLSX_DIR})"
    return True, f"{len(REQUIRED_EXCELS)}개 모두 존재 ({XLSX_DIR})"


def check_locks():
    """'~$' 로 시작하는 엑셀 잠금 파일이 있으면 경고."""
    locks = sorted(p.name for p in XLSX_DIR.glob("~$*.xlsx")) + sorted(
        p.name for p in XLSX_DIR.glob("~$*.xls")
    )
    if locks:
        return False, (
            f"잠금 파일 {len(locks)}개 감지: {locks}. "
            f"엑셀로 열린 파일을 닫은 뒤 다시 실행하세요 (import_excel.py, add_school.py 등 쓰기 작업이 실패할 수 있음)."
        )
    return True, "잠금 파일 없음"


def main():
    print("=" * 60)
    print("schoolmap 개발 환경 진단")
    print("=" * 60)

    checks = [
        ("1. Python 패키지 (openpyxl)", check_openpyxl, True),
        ("2. Node.js / npx", check_node, True),
        ("3. Cloudflare API 토큰", check_cloudflare_token, True),
        ("4. 필수 엑셀 7개", check_excels, True),
        ("5. 엑셀 잠금 파일 (~$)", check_locks, False),  # 경고만, 필수 아님
    ]

    fails = 0
    warns = 0
    for label, fn, required in checks:
        ok, msg = fn()
        if ok:
            mark = OK
        elif required:
            mark = FAIL
            fails += 1
        else:
            mark = WARN
            warns += 1
        print(f"{mark} {label}")
        print(f"     {msg}")

    print()
    print("=" * 60)
    if fails == 0 and warns == 0:
        print("모든 항목 통과. 작업 시작 가능합니다.")
    elif fails == 0:
        print(f"필수 항목 통과, 경고 {warns}개. 해결 후 진행 권장.")
    else:
        print(f"필수 항목 {fails}개 실패. 위 안내에 따라 해결 후 다시 실행하세요.")
    print("=" * 60)

    sys.exit(1 if fails > 0 else 0)


if __name__ == "__main__":
    main()
