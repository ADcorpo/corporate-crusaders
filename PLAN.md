# Corporate Crusader — Implementation Plan

## Repo
https://github.com/ADcorpo/corporate-crusaders  
Working directory: `/Users/benraby/Desktop/corporate-crusaders`

---

## Hardware
- **ESP32** via USB serial (`/dev/cu.usbserial-*`, auto-detected)
- **MPU-9250 IMU** — I2C, SDA=GPIO21, SCL=GPIO22, 3.3V
- **GY MAX4466 mic** — analog, GPIO34 (ADC)

---

## Current state of the code

### `corporate crusader/game.py`
- Loads title, rolling, and outcome images from subfolders
- Serial listener thread reads lines from ESP32, triggers on `"SCREAM"`
- State machine: `STATE_TITLE → STATE_ROLLING → STATE_OUTCOME → STATE_TITLE`
- Title pulses between two images every 500ms
- Rolling animates frames for 4–8s then picks a random outcome image
- Outcome displays for 10s then returns to title
- Debug print added: `print(f"serial: {repr(line)}")` — **remove before final demo**

### `scream_trigger/scream_trigger.ino`
- Reads mic peak over 50ms windows on GPIO34
- Sends `"SCREAM"` over serial if peak ≥ threshold (currently hardcoded to 4094)
- No IMU code yet

---

## What we're changing

### Work package 1 — ESP32 firmware rewrite (`scream_trigger.ino`)
**Branch:** `feature/esp32-imu-mic`

Replace the current sketch with one that:
1. Includes the MPU-9250 library (use `MPU9250` by Bolder Flight Systems or `SparkFun MPU-9250`)
2. On boot, samples IMU for ~500ms to record baseline euler angles (roll, pitch, yaw)
3. Each loop:
   - Reads IMU, computes deviation from baseline
   - If any axis deviates >45°, sends `TILT` once (debounced — won't re-send until device returns within 10° of baseline)
   - Reads mic peak over 50ms window on GPIO34
   - Sends `MIC:<value>` every loop (e.g. `MIC:1823`) — **thresholding moves to Python side**

Serial protocol summary:
- `TILT` — device has been tilted >45° from resting position
- `MIC:<0-4095>` — raw mic peak reading, sent continuously

---

### Work package 2 — game.py: replace SCREAM trigger with TILT
**Branch:** `feature/imu-game-trigger`  
**Depends on:** WP1 deployed to ESP32

Changes to `game.py`:
1. Replace `scream_event` with `tilt_event` (same `threading.Event` pattern)
2. Serial listener: parse `TILT` → set `tilt_event`; parse `MIC:<int>` → write int to a shared `mic_value` variable (use a `threading.Lock` or just an atomic int — fine for this use case)
3. Rename `STATE_TITLE` to `STATE_IDLE` (or keep name, just change trigger)
4. In idle state: wait for `tilt_event` instead of `scream_event` to transition to `STATE_ROLLING`
5. Remove the debug `repr(line)` print

---

### Work package 3 — game.py: countdown + scream sampling + benefits screens
**Branch:** `feature/scream-outcome`  
**Depends on:** WP2 merged

New states to add after `STATE_OUTCOME`:

```
STATE_OUTCOME (8s) 
  → STATE_COUNTDOWN 
  → STATE_SCREAM_SAMPLE 
  → STATE_BENEFITS or STATE_NO_BENEFITS 
  → STATE_IDLE
```

**STATE_COUNTDOWN:**
- Display text overlay on black background: `"Scream for a benefits package!"`
- Then animate: `"3"` (1s) → `"2"` (1s) → `"1"` (1s)
- Rendered with `pygame.font.SysFont` or a loaded TTF, centred on screen
- Transition to `STATE_SCREAM_SAMPLE`

**STATE_SCREAM_SAMPLE:**
- Sample `mic_value` for 1.5 seconds, track peak
- MIC threshold constant at top of file: `MIC_THRESHOLD = 2000` (tune during testing)
- If peak ≥ `MIC_THRESHOLD` → `STATE_BENEFITS`
- Else → `STATE_NO_BENEFITS`

**STATE_BENEFITS:**
- Black background, centred white text: `"YOU GOT BENEFITS"`
- Display for 4s → `STATE_IDLE`
- Easy to swap for an image later (just load and blit instead of drawing text)

**STATE_NO_BENEFITS:**
- Black background, centred white text: `"NO BENEFITS FOR YOU"`
- Display for 4s → `STATE_IDLE`
- Same — image swap ready

**Font rendering helper** (add once, reuse across states):
```python
def draw_centred_text(surface, text, size, colour=(255, 255, 255)):
    font = pygame.font.SysFont(None, size)
    img = font.render(text, True, colour)
    rect = img.get_rect(center=surface.get_rect().center)
    surface.blit(img, rect)
```

---

## Constants to add to top of game.py
```python
MIC_THRESHOLD = 2000        # tune: 0–4095
OUTCOME_DISPLAY_S = 8       # changed from 10
COUNTDOWN_STEP_S = 1.0
SCREAM_SAMPLE_S = 1.5
RESULT_DISPLAY_S = 4
```

---

## Suggested branch/PR order
1. `feature/esp32-imu-mic` → flash to ESP32, verify serial output, merge
2. `feature/imu-game-trigger` → test tilt-to-roll flow, merge
3. `feature/scream-outcome` → test full flow end to end, merge

---

## Notes
- Set up venv: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
- **Use `pygame-ce`, not `pygame`** — plain pygame lacks SDL_image and can't load JPEGs. `requirements.txt` pins `pygame-ce==2.5.7`.
- Run with: `source venv/bin/activate && python3 "corporate crusader/game.py"`
- Arduino IDE serial monitor must be **closed** before running game.py (port conflict)
- `scream_trigger.ino` also lives at `terrible_ideas/scream_trigger/` — the copy in the repo is the source of truth going forward
