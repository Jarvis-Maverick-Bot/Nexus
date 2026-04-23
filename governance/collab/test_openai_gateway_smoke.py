import json
from pathlib import Path

from governance.collab.llm_adapter import create_llm_adapter


def main() -> int:
    cfg = json.loads(Path('governance/collab/collab_config.json').read_text())
    llm = cfg['llm']
    adapter = create_llm_adapter(
        provider=llm['provider'],
        api_key_profile=llm['api_key_profile'],
        model=llm['model'],
        timeout_seconds=20,
        max_retries=0,
    )
    ok, text, err = adapter.generate(
        system_prompt='You are a concise assistant.',
        user_prompt='Reply with exactly: OPENCLAW_GATEWAY_OK'
    )
    print('ok=', ok)
    print('err=', err)
    print('text=', repr(text.strip()))
    return 0 if ok and text.strip() == 'OPENCLAW_GATEWAY_OK' else 1


if __name__ == '__main__':
    raise SystemExit(main())
