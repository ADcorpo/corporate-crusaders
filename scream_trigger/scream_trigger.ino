#include <Wire.h>

// ── Pin / bus config ─────────────────────────────────────────────────────────
const int MIC_PIN  = 34;
const int SDA_PIN  = 21;
const int SCL_PIN  = 22;
const int MPU_ADDR = 0x68;

// ── Tuning constants ─────────────────────────────────────────────────────────
const int   SAMPLE_WINDOW_MS = 50;
const float TILT_THRESHOLD   = 20.0f;  // degrees from baseline
const int   BASELINE_SAMPLES = 100;

// ── Globals ───────────────────────────────────────────────────────────────────
float baseAx = 0, baseAy = 0, baseAz = 0;
unsigned long lastPrintMs = 0;
const int PRINT_INTERVAL_MS = 250;  // 4 Hz

// ── MPU-9250 helpers ──────────────────────────────────────────────────────────
void mpuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

bool mpuReadAccel(float &ax, float &ay, float &az) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);  // ACCEL_XOUT_H
  if (Wire.endTransmission(false) != 0) return false;
  Wire.requestFrom(MPU_ADDR, 6);
  if (Wire.available() < 6) return false;
  int16_t rawX = (Wire.read() << 8) | Wire.read();
  int16_t rawY = (Wire.read() << 8) | Wire.read();
  int16_t rawZ = (Wire.read() << 8) | Wire.read();
  // ±2g range → 16384 LSB/g
  ax = rawX / 16384.0f;
  ay = rawY / 16384.0f;
  az = rawZ / 16384.0f;
  return true;
}

// Angle between two unit vectors via dot product, clamped for acos safety
float angleBetween(float ax, float ay, float az,
                   float bx, float by, float bz) {
  float dot = ax*bx + ay*by + az*bz;
  float magA = sqrtf(ax*ax + ay*ay + az*az);
  float magB = sqrtf(bx*bx + by*by + bz*bz);
  if (magA < 0.001f || magB < 0.001f) return 0.0f;
  float cosAngle = dot / (magA * magB);
  cosAngle = constrain(cosAngle, -1.0f, 1.0f);
  return degrees(acosf(cosAngle));
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);

  Wire.begin(SDA_PIN, SCL_PIN);
  mpuWrite(0x6B, 0x00);  // PWR_MGMT_1: wake up, use internal clock
  delay(100);

  // Verify WHO_AM_I
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 1);
  uint8_t whoami = Wire.available() ? Wire.read() : 0;
  if (whoami != 0x71 && whoami != 0x73 && whoami != 0x70) {
    Serial.print("IMU_ERROR:0x");
    Serial.println(whoami, HEX);
    while (true) delay(1000);
  }

  // Sample baseline gravity vector
  float sumX = 0, sumY = 0, sumZ = 0;
  int n = 0;
  while (n < BASELINE_SAMPLES) {
    float ax, ay, az;
    if (mpuReadAccel(ax, ay, az)) {
      sumX += ax; sumY += ay; sumZ += az;
      n++;
    }
    delay(5);
  }
  baseAx = sumX / n;
  baseAy = sumY / n;
  baseAz = sumZ / n;

  Serial.println("READY");
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  // ── IMU ───────────────────────────────────────────────────────────────────
  float ax, ay, az;
  if (mpuReadAccel(ax, ay, az)) {
    float deviation = angleBetween(ax, ay, az, baseAx, baseAy, baseAz);

    if (deviation >= TILT_THRESHOLD) {
      Serial.println("TILT");
    }
  }

  // ── Mic ───────────────────────────────────────────────────────────────────
  int peak = 0;
  unsigned long start = millis();
  while (millis() - start < SAMPLE_WINDOW_MS) {
    int v = analogRead(MIC_PIN);
    if (v > peak) peak = v;
  }

  // ── Throttled debug print at 4 Hz ────────────────────────────────────────
  unsigned long now = millis();
  if (now - lastPrintMs >= PRINT_INTERVAL_MS) {
    lastPrintMs = now;
    float ax2, ay2, az2;
    if (mpuReadAccel(ax2, ay2, az2)) {
      float dev = angleBetween(ax2, ay2, az2, baseAx, baseAy, baseAz);
      Serial.print("DEV:");
      Serial.print(dev, 1);
      Serial.print(" MIC:");
      Serial.println(peak);
    }
  }
}
