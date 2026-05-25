from pathlib import Path


def test_foundation_daemon_service_templates_are_default_off():
    systemd = Path("packaging/systemd/nexus-mq-foundation-daemon.service").read_text(encoding="utf-8")
    launchd = Path("packaging/launchd/com.nexus.mq-foundation-daemon.plist").read_text(encoding="utf-8")

    assert "WantedBy=" not in systemd
    assert "RunAtLoad" in launchd
    assert "<false/>" in launchd
    assert "DO NOT INSTALL OR ENABLE WITHOUT LATER ALEX AUTHORIZATION" in systemd
    assert "DO NOT LOAD OR START WITHOUT LATER ALEX AUTHORIZATION" in launchd
