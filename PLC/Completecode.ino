#include <P1AM.h>
#include <Ethernet.h>

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

// ==================== GLOBAL VARIABLES ====================

// Speed constants (12-bit: 0-4095 range)
const uint16_t lowSpeed = 1000;    // low speed forward
const uint16_t medSpeed = 2048;    // medium speed forward (~50%)
const uint16_t highSpeed = 3095;   // high speed forward

// Lower speeds for reverse (safety)
const uint16_t lowSpeedReverse = 800;   // low speed reverse
const uint16_t medSpeedReverse = 1500;  // medium speed reverse
const uint16_t highSpeedReverse = 2000;  // high speed reverse (capped)

// Ethernet setup
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress ip(192, 168, 1, 177);
unsigned int port = 5000;
EthernetServer tcpServer(port);

// Robot state
enum RobotState { 
    STOPPED, 
    AUTO_CYCLE,      // Automatic forward speed progression
    MANUAL_CONTROL   
};

RobotState currentState = STOPPED;
bool isForwardDirection = true; // true = forward, false = reverse

// ===== FIX: Added speed state tracking (was reading unreliable analog outputs) =====
uint16_t currentSpeed = 0; // Track current speed setting for state machine
// =================================================================================

unsigned long lastStateChange = 0;
const unsigned long stateDuration = 10000; // 10 seconds per speed

// ==================== DRIVE CONTROL FUNCTIONS ====================

void enableDriveA() {
    P1.writeDiscrete(HIGH, enableAControl);   // Enable drive
    P1.writeDiscrete(HIGH, brakeAControl);    // Release brake
}

void enableDriveB() {
    P1.writeDiscrete(HIGH, enableBControl);   // Enable drive  
    P1.writeDiscrete(HIGH, brakeBControl);    // Release brake
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
    // ===== FIX: Track speed state =====
    currentSpeed = 0;
    // ==================================
}

void setSpeed(uint16_t speedA, uint16_t speedB) {
    P1.writeAnalog(speedA, analogAControl);
    P1.writeAnalog(speedB, analogBControl);
    // ===== FIX: Track speed state (use speedA as primary reference) =====
    currentSpeed = speedA;
    // =====================================================================
}

void setSpeed(uint16_t speed) {
    setSpeed(speed, speed);
    // Note: currentSpeed tracking handled in setSpeed(speedA, speedB)
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

// ==================== MOTION FUNCTIONS ====================

void setForwardMotion() {
    enableDriveA();
    enableDriveB();
    setForwardDirection();
    setSpeed(medSpeed);
    // ===== FIX: Speed state tracked in setSpeed() =====
}

void setReverseMotion() {
    enableDriveA();
    enableDriveB();
    setReverseDirection();
    setSpeed(medSpeedReverse);
    // ===== FIX: Speed state tracked in setSpeed() =====
}

void performStandardTurn() {
    if (isForwardDirection) {
        setSpeed(lowSpeed, medSpeed);
    } else {
        setSpeed(lowSpeedReverse, medSpeedReverse);
    }
}

void performSharpTurn() {
    if (isForwardDirection) {
        setSpeed(0, medSpeed);
    } else {
        setSpeed(0, medSpeedReverse);
    }
}

// ==================== TCP COMMAND HANDLING ====================

void handleTCPClient() {
    EthernetClient client = tcpServer.available();
    if (client) {
        Serial.println("TCP Client connected");
        
        while (client.connected()) {
            if (client.available()) {
                String command = client.readStringUntil('\n');
                command.trim();
                Serial.print("Received TCP command: ");
                Serial.println(command);
                
                // Check if client wants to take control
                if (command.equalsIgnoreCase("TAKE_CONTROL")) {
                    currentState = MANUAL_CONTROL;
                    client.println("ACK: MANUAL CONTROL MODE");
                }
                // Command processing for MANUAL_CONTROL mode only
                else if (currentState == MANUAL_CONTROL) {
                    if (command.equalsIgnoreCase("FORWARD")) {
                        setForwardMotion();
                        client.println("ACK: MOVING FORWARD");
                    } 
                    else if (command.equalsIgnoreCase("REVERSE")) {
                        stopBothDrives(); // Stop before direction change
                        delay(100);       // Brief pause for safety
                        setReverseMotion();
                        client.println("ACK: MOVING REVERSE");
                    }
                    else if (command.equalsIgnoreCase("TURN")) {
                        performStandardTurn();
                        client.println("ACK: STANDARD TURN");
                    }
                    else if (command.equalsIgnoreCase("SHARP_TURN")) {
                        performSharpTurn();
                        client.println("ACK: SHARP TURN");
                    }
                    else if (command.equalsIgnoreCase("STOP")) {
                        stopBothDrives();
                        client.println("ACK: STOPPED");
                    }
                    else if (command.equalsIgnoreCase("SET_SPEED")) {
                        // Parse speed value if needed
                        setSpeed(medSpeed);
                        client.println("ACK: SPEED SET TO MEDIUM");
                    }
                    else if (command.equalsIgnoreCase("RELEASE_CONTROL")) {
                        currentState = AUTO_CYCLE;
                        client.println("ACK: RETURNING TO AUTO MODE");
                    }
                    else {
                        client.println("NACK: Unknown command in MANUAL mode");
                    }
                } 
                else if (currentState == AUTO_CYCLE) {
                    if (command.equalsIgnoreCase("STOP")) {
                        currentState = STOPPED;
                        stopBothDrives();
                        client.println("ACK: STOPPED FROM AUTO MODE");
                    }
                    else {
                        client.println("NACK: Commands only accepted in MANUAL_CONTROL mode");
                    }
                }
            }
        }
        client.stop();
        Serial.println("TCP Client disconnected");
        
        // If TCP disconnects and we were in manual mode, return to auto
        if (currentState == MANUAL_CONTROL) {
            currentState = AUTO_CYCLE;
            Serial.println("Auto mode resumed after TCP disconnect");
        }
    }
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
        currentState = STOPPED;
        stopBothDrives();
        Serial.println("EMERGENCY STOP ACTIVATED");
        return;
    }
    
    switch(currentState) {
        case STOPPED:
            if (startPressed) {
                currentState = AUTO_CYCLE;
                lastStateChange = currentMillis;
                enableDriveA();
                enableDriveB();
                setForwardDirection();
                setSpeed(lowSpeed);
                Serial.println("STARTED: Auto cycle - LOW speed forward");
            }
            break;
            
        case AUTO_CYCLE:
            if (stopPressed) {
                currentState = STOPPED;
                stopBothDrives();
                Serial.println("STOPPED: Hardware stop button");
            }
            else {
                // ===== FIX: CRITICAL BUG - Original code read analog OUTPUT values which is unreliable =====
                // Changed to use currentSpeed state variable (added at line 52) instead of P1.readAnalog()
                // P1.readAnalog() is for reading INPUT channels; cannot reliably read back OUTPUT values
                // This fix ensures speed progression actually works as intended
                // =======================================================================================
                
                // Handle automatic speed progression
                if (currentMillis - lastStateChange >= stateDuration) {
                    // Cycle through forward speeds
                    if (currentSpeed == lowSpeed) {
                        setSpeed(medSpeed);
                        Serial.println("SPEED CHANGE: MEDIUM speed forward");
                    }
                    else if (currentSpeed == medSpeed) {
                        setSpeed(highSpeed);
                        Serial.println("SPEED CHANGE: HIGH speed forward");
                    }
                    else {
                        setSpeed(lowSpeed);
                        Serial.println("SPEED CYCLE: Restarting at LOW speed");
                    }
                    lastStateChange = currentMillis;
                }
            }
            break;
            
        case MANUAL_CONTROL:
            // TCP commands handled separately
            if (stopPressed) {
                currentState = STOPPED;
                stopBothDrives();
                Serial.println("STOPPED: Hardware stop button (overrode TCP control)");
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
    
    // Initialize Ethernet
    Ethernet.begin(mac, ip);
    tcpServer.begin();
    Serial.print("TCP Server listening on ");
    Serial.println(ip);
    
    Serial.println("System initialized - Press START button to begin auto cycle");
}

void loop() {
    // Handle TCP clients
    handleTCPClient();
    
    // Handle robot state machine
    handleRobotStateMachine();
    
    // Small delay
    delay(100);
}
