const int MIC_PIN = 34;
const int SAMPLE_WINDOW_MS = 50;
const int THRESHOLD = 4094;  // tune this: 0-4095, higher = louder required
const int COOLDOWN_MS = 2000;

unsigned long lastTriggerTime = 0;

void setup() {
  Serial.begin(115200);
  delay(2000);  // let ADC settle after boot
}

void loop() {
  unsigned long start = millis();
  int peak = 0;

  while (millis() - start < SAMPLE_WINDOW_MS) {
    int val = analogRead(MIC_PIN);
    if (val > peak) peak = val;
  }

  if (peak >= THRESHOLD && millis() - lastTriggerTime > COOLDOWN_MS) {
    Serial.println("SCREAM");
    lastTriggerTime = millis();
  }
}