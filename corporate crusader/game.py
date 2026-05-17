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
    os.path.join(ASSETS, "rolling", "black.jpg"),
    os.path.join(ASSETS, "rolling", "pink.jpg"),
    os.path.join(ASSETS, "rolling", "white.jpg"),
]
OUTCOME_IMAGES = [
    os.path.join(ASSETS, "outcomes", f"outcome{i}.jpg") for i in range(1, 9)
]

TITLE_PULSE_MS = 500
ROLLING_FRAME_MS = 50
OUTCOME_DISPLAY_S = 10
SERIAL_BAUD = 115200

STATE_TITLE = "title"
STATE_ROLLING = "rolling"
STATE_OUTCOME = "outcome"


def find_serial_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if "usbserial" in p.device.lower() or "wchusbserial" in p.device.lower():
            return p.device
    return None


def serial_listener(scream_event, stop_event):
    port = find_serial_port()
    if port is None:
        print("No serial port found — running without mic input.")
        return
    try:
        ser = serial.Serial(port, SERIAL_BAUD, timeout=1)
        print(f"Listening on {port}")
        while not stop_event.is_set():
            try:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    print(f"serial: {repr(line)}")
                if line == "SCREAM":
                    scream_event.set()
            except Exception:
                pass
        ser.close()
    except Exception as e:
        print(f"Serial error: {e} — running without mic input.")


def load_images(screen):
    w, h = screen.get_size()

    def load(paths):
        result = []
        for p in paths:
            img = pygame.image.load(p).convert_alpha()
            img = pygame.transform.scale(img, (w, h))
            result.append(img)
        return result

    return (
        load(TITLE_IMAGES),
        load(ROLLING_IMAGES),
        load(OUTCOME_IMAGES),
    )


def main():
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Corporate Crusader")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    title_imgs, rolling_imgs, outcome_imgs = load_images(screen)

    scream_event = threading.Event()
    stop_event = threading.Event()
    listener = threading.Thread(
        target=serial_listener, args=(scream_event, stop_event), daemon=True
    )
    listener.start()

    state = STATE_TITLE
    title_idx = 0
    rolling_idx = 0
    outcome_img = None

    last_title_flip = time.time()
    last_rolling_flip = time.time()
    roll_end_time = None
    outcome_start_time = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        now = time.time()

        if state == STATE_TITLE:
            if now - last_title_flip >= TITLE_PULSE_MS / 1000:
                title_idx = 1 - title_idx
                last_title_flip = now

            if scream_event.is_set():
                scream_event.clear()
                state = STATE_ROLLING
                rolling_idx = 0
                last_rolling_flip = now
                roll_end_time = now + random.randint(4, 8)

            screen.blit(title_imgs[title_idx], (0, 0))

        elif state == STATE_ROLLING:
            if now - last_rolling_flip >= ROLLING_FRAME_MS / 1000:
                rolling_idx = (rolling_idx + 1) % len(rolling_imgs)
                last_rolling_flip = now

            if now >= roll_end_time:
                outcome_img = random.choice(outcome_imgs)
                outcome_start_time = now
                state = STATE_OUTCOME

            screen.blit(rolling_imgs[rolling_idx], (0, 0))

        elif state == STATE_OUTCOME:
            if now - outcome_start_time >= OUTCOME_DISPLAY_S:
                state = STATE_TITLE
                title_idx = 0
                last_title_flip = now
                scream_event.clear()

            screen.blit(outcome_img, (0, 0))

        pygame.display.flip()
        clock.tick(60)

    stop_event.set()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
