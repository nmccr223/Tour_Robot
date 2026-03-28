#include <P1AM.h>

// ==================== CHANNEL DEFINITIONS ====================

// Control signals (outputs) - slot 1
channelLabel enableAControl = {1, 1};    // slot 1, channel 1
channelLabel brakeAControl = {1, 2};     // slot 1, channel 2  
channelLabel directionAControl = {1, 3}; // slot 1, channel 3

channelLabel enableBControl = {1, 4};    // slot 1, channel 4
channelLabel brakeBControl = {1, 5};     // slot 1, channel 5
channelLabel directionBControl = {1, 6}; // slot 1, channel 6

// Analog speed control - slot 2
channelLabel analogAControl = {2, 1}; // Drive A speed - slot 2, channel 1
channelLabel analogBControl = {2, 2}; // Drive B speed - slot 2, channel 2

// Error signals (inputs) - slot 2
channelLabel faultASignal = {2, 1};      // slot 2, channel 1
channelLabel readyASignal = {2, 2};     // slot 2, channel 2
channelLabel ebrakeASignal = {2, 3};    // slot 2, channel 3

channelLabel faultBSignal = {2, 4};      // slot 2, channel 4
channelLabel readyBSignal = {2, 5};     // slot 2, channel 5
channelLabel ebrakeBSignal = {2, 6};    // slot 2, channel 6

// Push Button Switches - slot 3
channelLabel startSignal = {3, 1};  // Digital input - slot 3, channel 1
channelLabel stopSignal = {3, 2};   // Digital input - slot 3, channel 2  
channelLabel emergencystopSignal = {3, 3}; // Digital input - slot 3, channel 3

// Speed constants (12-bit: 0-4095 range)
const uint16_t lowSpeed = 1000;    // low speed
const uint16_t medSpeed = 2048;    // medium speed (~50%)
const uint16_t highSpeed = 3095;   // high speed max

// ==================== STATE VARIABLES ====================

enum RobotState { STOPPED, RUNNING_LOW, RUNNING_MED, RUNNING_HIGH };
RobotState currentState = STOPPED;
bool isForwardDirection = true; // true = forward, false = reverse

unsigned long lastStateChange = 0;
const unsigned long stateDuration = 10000; // 10 seconds per speed

// ==================== DRIVE CONTROL FUNCTIONS ====================

void enableDriveA() {
    P1.writeDiscrete(HIGH, enableAControl);   // Enable drive
    P1.writeDiscrete(HIGH, brakeAControl);    // Release brake
    P1.writeDiscrete(LOW, directionAControl); // Forward direction
}

void enableDriveB() {
    P1.writeDiscrete(HIGH, enableBControl);   // Enable drive  
    P1.writeDiscrete(HIGH, brakeBControl);    // Release brake
    P1.writeDiscrete(HIGH, directionBControl); // Forward direction
}

void disableDriveA() {
    P1.writeDiscrete(LOW, enableAControl);   // Disable drive
    P1.writeDiscrete(LOW, brakeAControl);      // Apply brake
}

void disableDriveB() {
    P1.writeDiscrete(LOW, enableBControl);   // Disable drive
    P1.writeDiscrete(LOW, brakeBControl);      // Apply brake
}

void stopBothDrives() {
    P1.writeAnalog(0, analogAControl);
    P1.writeAnalog(0, analogBControl);
    disableDriveA();
    disableDriveB();
}

void setSpeed(uint16_t speed) {
    P1.writeAnalog(speed, analogAControl);
    P1.writeAnalog(speed, analogBControl);
}
void setForwardDirection() {
    P1.writeDiscrete(HIGH, directionAControl);
    P1.writeDiscrete(HIGH, directionBControl);
    isForwardDirection = true;
}

void setReverseDirection() {
    P1.writeDiscrete(LOW, directionAControl);
    P1.writeDiscrete(LOW, directionBControl);
    isForwardDirection = false;
}
void setForwardMotion() {
    enableDriveA();
    enableDriveB();
    setForwardDirection();
    setSpeed(medSpeed);
}

void setReverseMotion() {
    enableDriveA();
    enableDriveB();
    setReverseDirection();
    setSpeed(medSpeed);
}

// ==================== STATE MACHINE ====================

void handleRobotStateMachine() {
    unsigned long currentMillis = millis();
    
    // Read button states
    bool startPressed = P1.readDiscrete(startSignal);  // Normally open - pressed = HIGH
    bool stopPressed = !P1.readDiscrete(stopSignal); // Invert for NC stop button
    bool emergencyStopActive = !P1.readDiscrete(emergencystopSignal); // NC - pressed = LOW
    
    // Emergency stop has highest priority
    if (emergencyStopActive) {
        stopBothDrives();
        currentState = STOPPED;
        lastStateChange = currentMillis;
        return;
    }
    
    switch(currentState) {
        case STOPPED:
            if (startPressed) {
                currentState = RUNNING_LOW;
                lastStateChange = currentMillis;
                enableDriveA();
                enableDriveB();
                setSpeed(lowSpeed);
                Serial.println("STARTED: Running at LOW speed");
            }
            break;
            
        case RUNNING_LOW:
            if (stopPressed) {
                currentState = STOPPED;
                stopBothDrives();
                Serial.println("STOPPED: Motors disabled");
            }
            else if (currentMillis - lastStateChange >= stateDuration) {
                currentState = RUNNING_MED;
                lastStateChange = currentMillis;
                setSpeed(medSpeed);
                Serial.println("SPEED CHANGE: Running at MEDIUM speed");
            }
            break;
            
        case RUNNING_MED:
            if (stopPressed) {
                currentState = STOPPED;
                stopBothDrives();
                Serial.println("STOPPED: Motors disabled");
            }
            else if (currentMillis - lastStateChange >= stateDuration) {
                currentState = RUNNING_HIGH;
                lastStateChange = currentMillis;
                setSpeed(highSpeed);
                Serial.println("SPEED CHANGE: Running at HIGH speed");
            }
            break;
            
        case RUNNING_HIGH:
            if (stopPressed) {
                currentState = STOPPED;
                stopBothDrives();
                Serial.println("STOPPED: Motors disabled");
            }
            else if (currentMillis - lastStateChange >= stateDuration) {
                currentState = RUNNING_LOW;
                lastStateChange = currentMillis;
                setSpeed(lowSpeed);
                Serial.println("SPEED CYCLE: Restarting at LOW speed");
            }
            break;
    }
}

// ==================== SETUP AND MAIN LOOP ====================

void setup() {
    Serial.begin(115200);
    while (!P1.init()) {
        ; // Wait for Modules to Sign on
    }
    
    // Initial startup check for I/O
    bool allLow = true; 
    
    const channelLabel controlPins[] = {enableAControl, enableBControl, 
                                        brakeAControl, brakeBControl,
                                        directionAControl, directionBControl};
    
    const channelLabel errorPins[] = {faultASignal, readyASignal, ebrakeASignal,
                                        faultBSignal, readyBSignal, ebrakeBSignal};
    
    // Read outputs and check for active signals
    for (int i = 0; i < sizeof(controlPins) / sizeof(controlPins[0]); i++) {
        if (P1.readDiscrete(controlPins[i]) == HIGH) {
            Serial.print("Warning: Unexpected active signal on control pin ");
            Serial.println(i);
            allLow = false;
        }
    }
    
    // Read inputs (error signals)
    for (int i = 0; i < sizeof(errorPins) / sizeof(errorPins[0]); i++) {
            if (P1.readDiscrete(errorPins[i])) {
                Serial.print("Warning: Unexpected active signal on error pin ");
                Serial.println(i);
                allLow = false;
            }
        }
    
    // Print result
    if (allLow) {
        Serial.println("I/O CHECK: ALL LOW SYSTEM READY");
    } else {
        Serial.println("I/O CHECK: NOT ALL LOW");
    }
    
    // Set initial states
    stopBothDrives();
    Serial.println("System initialized - Press START button to begin");
}

void loop() {
    // Handle robot state machine
    handleRobotStateMachine();
    
    // Add small delay to prevent overwhelming the system
    delay(100);
}
