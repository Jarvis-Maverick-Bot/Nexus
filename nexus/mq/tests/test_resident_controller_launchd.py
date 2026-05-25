from pathlib import Path


def test_resident_controller_launchd_template_default_off():
    template = Path("packaging/launchd/com.nexus.resident-controller.example.plist")

    text = template.read_text(encoding="utf-8")

    assert "<key>Disabled</key>" in text
    assert "<true/>" in text
    assert "NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF" in text
    assert "ProgramArguments" in text
    assert "start-once" not in text
