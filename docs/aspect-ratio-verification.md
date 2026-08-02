# Verify 4:3 master signaling

VHScribe keeps the encoded standard-definition dimensions and signals how square-pixel displays
should render them. It does not resize existing files.

For a newly created recording, run:

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,sample_aspect_ratio,display_aspect_ratio,r_frame_rate \
  -of default=noprint_wrappers=1 '/path/to/new-recording.mkv'
```

Expected PAL values include `width=720`, `height=576`, `sample_aspect_ratio=16:15`,
`display_aspect_ratio=4:3`, and `r_frame_rate=25/1`. NTSC uses 720×480, 8:9, 4:3, and
30000/1001.

Also inspect a short test in VLC and the target browser/Jellyfin client. Players should present a
4:3 picture without requiring a manual aspect override. These interactive client checks are
acceptance tests; `ffprobe` is the machine-verifiable source for encoded metadata.
