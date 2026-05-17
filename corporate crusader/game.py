import pygame
import serial
import serial.tools.list_ports
import threading
import random
import time
import sys
import os

ASSETS = os.path.dirname(os.path.abspath(__file__))

TITLE_IMAGES = [
    os.path.join(ASSETS, "title", "title.jpg"),
    os.path.join(ASSETS, "title", "tytle 2.jpg"),
]
ROLLING_IMAGES = [
    # os.path.join(ASSETS, "rolling", "black.jpg"),
    # os.path.join(ASSETS, "rolling", "pink.jpg"),
    # os.path.join(ASSETS, "rolling", "white.jpg"),
    os.path.join(ASSETS, "rolling", "transparent.png"),
]
OUTCOME_IMAGES = [
    os.path.join(ASSETS, "outcomes", f"outcome{i}.jpg") for i in range(1, 9)
]
SLOT1_IMAGES = [
    os.path.join(ASSETS, "outcomes/slot1", f"{i}.png") for i in range(0, 7)
]
SLOT2_IMAGES = [
    os.path.join(ASSETS, "outcomes/slot2", f"{i}.png") for i in range(0, 8)
]
SLOT3_IMAGES = [
    os.path.join(ASSETS, "outcomes/slot3", f"{i}.png") for i in range(0, 8)
]
SLOT4_IMAGES = [
    os.path.join(ASSETS, "outcomes/slot4", f"{i}.png") for i in range(0, 8)
]


# ── Tuning ───────────────────────────────────────────────────────────────────
TITLE_PULSE_MS   = 500
ROLLING_FRAME_MS = 50
OUTCOME_DISPLAY_S  = 8
COUNTDOWN_PROMPT_S = 3.0
COUNTDOWN_STEP_S   = 1.0
SCREAM_SAMPLE_S    = 1.5
RESULT_DISPLAY_S   = 6
MIC_THRESHOLD      = 2000   # 0–4095; tune during testing
SERIAL_BAUD        = 115200

# ── States ───────────────────────────────────────────────────────────────────
STATE_TITLE        = "title"
STATE_ROLLING      = "rolling"
STATE_OUTCOME      = "outcome"
STATE_COUNTDOWN    = "countdown"
STATE_SCREAM_SAMPLE = "scream_sample"
STATE_BENEFITS     = "benefits"
STATE_NO_BENEFITS  = "no_benefits"


# ── Serial ───────────────────────────────────────────────────────────────────
def find_serial_port():
    for p in serial.tools.list_ports.comports():
        if "usbserial" in p.device.lower() or "wchusbserial" in p.device.lower():
            return p.device
    return None


def serial_listener(tilt_event, mic_value, mic_lock, stop_event):
    port = find_serial_port()
    if port is None:
        print("No serial port found — running without hardware input.")
        return
    try:
        ser = serial.Serial(port, SERIAL_BAUD, timeout=1)
        print(f"Listening on {port}")
        while not stop_event.is_set():
            try:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line == "TILT":
                    tilt_event.set()
                elif line.startswith("MIC:"):
                    try:
                        val = int(line[4:])
                        with mic_lock:
                            mic_value[0] = val
                    except ValueError:
                        pass
            except Exception:
                pass
        ser.close()
    except Exception as e:
        print(f"Serial error: {e} — running without hardware input.")


# ── Assets ───────────────────────────────────────────────────────────────────
def load_images(screen):
    w, h = screen.get_size()

    def load(paths):
        result = []
        for p in paths:
            img = pygame.image.load(p).convert_alpha()
            img = pygame.transform.scale(img, (w, h))
            result.append(img)
        return result

    return load(TITLE_IMAGES), load(ROLLING_IMAGES), load(OUTCOME_IMAGES)

def load_slot_images():
    def load(paths):
        result = []
        for p in paths:
            img = pygame.image.load(p).convert_alpha()
            result.append(img)
        return result

    return (
        load(SLOT1_IMAGES),
        load(SLOT2_IMAGES),
        load(SLOT3_IMAGES),
        load(SLOT4_IMAGES),
    )
    

# ── Drawing helpers ───────────────────────────────────────────────────────────
def draw_centred_text(surface, text, size, colour=(255, 255, 255)):
    font = pygame.font.SysFont(None, size)
    img = font.render(text, True, colour)
    rect = img.get_rect(center=surface.get_rect().center)
    surface.blit(img, rect)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((1280, 800), pygame.FULLSCREEN)
    pygame.display.set_caption("Corporate Crusader")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    title_imgs, rolling_imgs, outcome_imgs = load_images(screen)

    slot1_imgs, slot2_imgs, slot3_imgs, slot4_imgs = load_slot_images()

    scream_event = threading.Event()
    tilt_event = threading.Event()
    stop_event = threading.Event()
    mic_value  = [0]   # single-element list so listener can write to it
    mic_lock   = threading.Lock()

    listener = threading.Thread(
        target=serial_listener,
        args=(tilt_event, mic_value, mic_lock, stop_event),
        daemon=True,
    )
    listener.start()

    state        = STATE_TITLE
    title_idx    = 0
    rolling_idx  = 0
    outcome_img  = None

    last_title_flip   = time.time()
    last_rolling_flip = time.time()
    roll_end_time     = None
    state_start       = None   # generic state-entry timestamp
    countdown_step    = 0      # which digit we're showing (0=prompt, 1=3, 2=2, 3=1)
    scream_peak       = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                scream_event.set()

        now = time.time()
        screen.fill((0, 0, 0))

        # ── Title ─────────────────────────────────────────────────────────────
        if state == STATE_TITLE:
            if now - last_title_flip >= TITLE_PULSE_MS / 1000:
                title_idx = 1 - title_idx
                last_title_flip = now

            if tilt_event.is_set():
                tilt_event.clear()
                state = STATE_ROLLING
                rolling_idx = 0
                last_rolling_flip = now
                roll_end_time = now + random.randint(4, 8)

            screen.blit(title_imgs[title_idx], (0, 0))

        # ── Rolling ───────────────────────────────────────────────────────────
        elif state == STATE_ROLLING:
            if now - last_rolling_flip >= ROLLING_FRAME_MS / 1000:
                screen.blit(random.choice(slot1_imgs), (165, 430))
                screen.blit(random.choice(slot2_imgs), (690, 430))
                screen.blit(random.choice(slot3_imgs), (1195, 430))
                screen.blit(random.choice(slot4_imgs), (1720, 430))
                last_rolling_flip = now

            if now >= roll_end_time:
                #outcome_img = random.choice(outcome_imgs)
                outcome_start_time = now
                outcome_img = random.choice(outcome_imgs)
                state_start = now
                state = STATE_OUTCOME

            screen.blit(rolling_imgs[0], (0, 0))

        # ── Outcome ───────────────────────────────────────────────────────────
        elif state == STATE_OUTCOME:
            if now - state_start >= OUTCOME_DISPLAY_S:
                state_start    = now
                countdown_step = 0
                state = STATE_COUNTDOWN

            screen.blit(outcome_img, (0, 0))

        # ── Countdown ─────────────────────────────────────────────────────────
        elif state == STATE_COUNTDOWN:
            elapsed = now - state_start

            # Prompt holds for COUNTDOWN_PROMPT_S, then digits 3/2/1 for COUNTDOWN_STEP_S each
            if elapsed < COUNTDOWN_PROMPT_S:
                draw_centred_text(screen, "Scream for a benefits package in...", 72)
            else:
                digit_elapsed = elapsed - COUNTDOWN_PROMPT_S
                digit_step = int(digit_elapsed / COUNTDOWN_STEP_S)
                if digit_step == 0:
                    draw_centred_text(screen, "3", 200)
                elif digit_step == 1:
                    draw_centred_text(screen, "2", 200)
                elif digit_step == 2:
                    draw_centred_text(screen, "1", 200)
                else:
                    scream_peak = 0
                    state_start = now
                    state = STATE_SCREAM_SAMPLE

        # ── Scream sample ─────────────────────────────────────────────────────
        elif state == STATE_SCREAM_SAMPLE:
            with mic_lock:
                val = mic_value[0]
            if val > scream_peak:
                scream_peak = val

            draw_centred_text(screen, "SCREAM!", 200)

            if now - state_start >= SCREAM_SAMPLE_S:
                state_start = now
                state = STATE_BENEFITS if scream_peak >= MIC_THRESHOLD else STATE_NO_BENEFITS

        # ── Benefits ──────────────────────────────────────────────────────────
        elif state == STATE_BENEFITS:
            draw_centred_text(screen, "YOU GOT BENEFITS", 120)
            if now - state_start >= RESULT_DISPLAY_S:
                state = STATE_TITLE
                title_idx = 0
                last_title_flip = now
                tilt_event.clear()

        # ── No benefits ───────────────────────────────────────────────────────
        elif state == STATE_NO_BENEFITS:
            draw_centred_text(screen, "NO BENEFITS FOR YOU", 100)
            if now - state_start >= RESULT_DISPLAY_S:
                state = STATE_TITLE
                title_idx = 0
                last_title_flip = now
                tilt_event.clear()

        pygame.display.flip()
        clock.tick(60)

    stop_event.set()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
