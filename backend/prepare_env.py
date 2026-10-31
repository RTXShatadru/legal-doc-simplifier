"""Generate a private local session secret without printing or replacing credentials."""
from pathlib import Path
import re
import secrets
p=Path(__file__).resolve().parent.parent/'.env'
s=p.read_text(encoding='utf-8-sig')
if re.search(r'^JWT_SECRET=\s*$',s,re.M):
    s=re.sub(r'^JWT_SECRET=\s*$',lambda _: 'JWT_SECRET='+secrets.token_urlsafe(48),s,flags=re.M)
    p.write_text(s,encoding='utf-8')
