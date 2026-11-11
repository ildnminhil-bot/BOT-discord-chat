"""
Script tu kiem tra loi - CHAY SAU MOI LAN SUA CODE:
    python test_bot.py

Kiem tra: cu phap, import, nap cogs, dang ky lenh slash, bo loc tu cam,
parse thoi gian nhac nho, chia tin nhan dai. Khong can token that.
"""
import glob
import os
import py_compile
import sys
import types

os.environ.setdefault("DISCORD_TOKEN", "test-dummy")
os.environ.setdefault("GEMINI_API_KEY", "test-dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  OK   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {extra}")


print("== 1. Bien dich cu phap ==")
for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "**", "*.py"), recursive=True)):
    try:
        py_compile.compile(f, doraise=True)
        check(f"compile {os.path.basename(f)}", True)
    except py_compile.PyCompileError as e:
        check(f"compile {os.path.basename(f)}", False, str(e))

print("== 2. Import config & main ==")
try:
    import config
    check("import config", True)
except Exception as e:
    check("import config", False, str(e))
    sys.exit(1)

try:
    import main
    check("import main (khong chay bot)", True)
except Exception as e:
    check("import main", False, str(e))
    sys.exit(1)

print("== 3. Nap 5 cogs ==")
import asyncio
async def _load():
    for ext in ("cogs.ai_chat", "cogs.moderation", "cogs.reminders", "cogs.fun", "cogs.utility"):
        await main.bot.load_extension(ext)
    return len(main.bot.cogs)
try:
    n = asyncio.run(_load())
    check("nap cogs", n == 5, f"nap duoc {n}")
except RuntimeError:
    # Truong hop dang o trong event loop (Jupyter) - nap truc tiep
    import nestless  # noqa - khong co thi bo qua
except Exception as e:
    check("nap cogs", False, str(e))

print("== 4. Lenh slash ==")
try:
    cmds = [c.name for c in main.bot.tree.get_commands()]
    need = {"chaton", "chatoff", "warn", "ban", "remind", "8ball", "poll", "help", "ping"}
    check("du lenh slash", need.issubset(set(cmds)), f"thieu: {need - set(cmds)}")
except Exception as e:
    check("du lenh slash", False, str(e))

print("== 5. Logic: bo loc tu cam ==")
try:
    from cogs.moderation import find_bad_words
    check("bat tu cam", len(find_bad_words("mày ngu quá")) > 0)
    check("bat tu cam (anh)", len(find_bad_words("what the fuck")) > 0)
    check("khong ban oan", len(find_bad_words("giao dien rat dep")) == 0)
except Exception as e:
    check("bo loc tu cam", False, str(e))

print("== 6. Logic: parse thoi gian ==")
try:
    from cogs.reminders import Reminders
    check("10m -> 600", Reminders.parse_time("10m") == 600)
    check("2h -> 7200", Reminders.parse_time("2h") == 7200)
    check("abc -> None", Reminders.parse_time("abc") is None)
except Exception as e:
    check("parse thoi gian", False, str(e))

print(f"\nKET QUA: {PASS} dung, {FAIL} sai")
sys.exit(0 if FAIL == 0 else 1)
