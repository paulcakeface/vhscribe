from app.config import Settings
from app.ffmpeg import build_record_command, parse_progress


def test_parse_ffmpeg_progress() -> None:
    updates = parse_progress(
        [
            "frame=125\n",
            "fps=25.0\n",
            "total_size=123456\n",
            "out_time_us=5000000\n",
            "progress=continue\n",
        ]
    )
    assert len(updates) == 1
    assert updates[0]["frame"] == 125.0
    assert updates[0]["fps"] == 25.0
    assert updates[0]["total_size"] == 123456.0
    assert updates[0]["elapsed_seconds"] == 5.0


def test_record_command_reads_each_capture_input_once(tmp_path) -> None:
    settings = Settings(capture_dir=tmp_path)
    command = build_record_command(settings, tmp_path / "capture.part.mkv")
    assert command.count(settings.video_device) == 1
    assert command.count(settings.audio_device) == 1
    assert "split=2" in " ".join(command)
    assert "-f" in command
    assert "matroska" in command


def test_record_command_signals_4_3_without_resizing_master(tmp_path) -> None:
    settings = Settings(capture_dir=tmp_path)
    command = build_record_command(settings, tmp_path / "capture.part.mkv")
    filter_graph = command[command.index("-filter_complex") + 1]
    assert "[vmastersrc]setsar=16/15[vmain]" in filter_graph
    assert "[vprevsrc]scale=640:480" in filter_graph
    assert "[vmastersrc]scale=" not in filter_graph
    assert command[command.index("-aspect") + 1] == "4:3"


def test_ntsc_record_command_preserves_ntsc_resolution(tmp_path) -> None:
    settings = Settings(
        capture_dir=tmp_path,
        video_standard="NTSC",
        video_size="720x480",
        video_fps="30000/1001",
        video_gop=30,
        master_sar="8/9",
    )
    command = build_record_command(settings, tmp_path / "capture.part.mkv")
    filter_graph = command[command.index("-filter_complex") + 1]
    assert command[command.index("-video_size") + 1] == "720x480"
    assert "setsar=8/9" in filter_graph
    assert command[command.index("-r") + 1] == "30000/1001"
