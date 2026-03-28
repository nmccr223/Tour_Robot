// TOUR ROBOT CODE
// CONTROLLER. P1AM-200 CPU, P1AM-ETH-ETHERNET CARD,I/O CARDS-P1-15CDD2,ANALOG CARD-P1-04DAL-2
// ELECTROCRAFT DRIVES A & B (CPP-A24V80-SA-CAN)
#include <P1AM.h>
#include <Ethernet.h>

// Ethernet setup
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress ip(192, 168, 1, 177); // Change as needed
unsigned int port = 5000;

EthernetServer tcpServer(port);

// Timing variables for non-blocking client check
unsigned long lastCheck = 0;
const unsigned long checkInterval = 100; // ms

// Define channel labels for control signals (outputs)
// DRIVE A 
channelLabel enableAControl = {1, 1};    // slot 1, channel 1
channelLabel brakeAControl = {1, 2};     // slot 1, channel 2  
channelLabel directionAControl = {1, 3}; // slot 1, channel 3 
//direction control can be changed in the program or wiring to consider
// DRIVE B
channelLabel enableBControl = {1, 4};    // slot 1, channel 4
channelLabel brakeBControl = {1, 5};     // slot 1, channel 5
channelLabel directionBControl = {1, 6}; // slot 1, channel 6

// ANALOG CARD SIGNALS (12-bit: 0-4095 range)
channelLabel analogAControl = {2, 1}; // Drive A speed - slot 3, channel 1
channelLabel analogBControl = {2, 2}; // Drive B speed - slot 3, channel 2

// Define channel labels for error signals (inputs)
// DRIVE A 
channelLabel faultASignal = {2, 1};      // slot 2, channel 1
channelLabel readyASignal = {2, 2};     // slot 2, channel 2
channelLabel ebrakeASignal = {2, 3};    // slot 2, channel 3

// DRIVE B
channelLabel faultBSignal = {2, 4};      // slot 2, channel 4
channelLabel readyBSignal = {2, 5};     // slot 2, channel 5
channelLabel ebrakeBSignal = {2, 6};    // slot 2, channel 6

// ROBOT LIGHTS
// motion lights
channelLabel redMControl = {3, 4};
channelLabel yellowMControl = {3, 5};  
channelLabel greenMControl = {3, 6};

// status lights
channelLabel redSControl = {3, 7};
channelLabel yellowSControl = {3, 8};
channelLabel greenSControl = {3, 9};

// Push Button Switches/ control inputs
channelLabel startSignal = {3, 1};  // Digital input
channelLabel stopSignal = {3, 2};   // Digital input  
channelLabel emergencystopSignal = {3, 3}; // Digital input 

// Speed constants (12-bit: 0-4095 range)
const uint16_t lowSpeed = 1000;    // low speed
const uint16_t medSpeed = 2048;    // medium speed (~50%)
const uint16_t highSpeed = 3095;   // high speed max

// Robot state
enum RobotState { STOPPED, FORWARD, TURNING };
RobotState currentState = STOPPED;

// ==================== SYSTEM STATUS FUNCTIONS ====================

bool isEmergencyStopActive() {
    return P1.readDiscrete(emergencystopSignal);
}

bool checkDriveAStatus() {
    bool noFault = !P1.readDiscrete(faultASignal);
    bool isReady = P1.readDiscrete(readyASignal);
    bool ebrakeOff = !P1.readDiscrete(ebrakeASignal);
    return noFault && isReady && ebrakeOff;
}

bool checkDriveBStatus() {
    bool noFault = !P1.readDiscrete(faultBSignal);
    bool isReady = P1.readDiscrete(readyBSignal);
    bool ebrakeOff = !P1.readDiscrete(ebrakeBSignal);
    return noFault && isReady && ebrakeOff;
}

bool areDrivesReady() {
    return checkDriveAStatus() && checkDriveBStatus();
}

// ==================== DRIVE CONTROL FUNCTIONS ====================

void enableDriveA() {
    P1.writeDiscrete(HIGH, enableAControl);   // Active LOW
    P1.writeDiscrete(HIGH, brakeAControl);    // Release brake
    P1.writeDiscrete(HIGH, directionAControl); // Forward direction
}

void enableDriveB() {
    P1.writeDiscrete(HIGH, enableBControl);   // Active LOW  
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

// ==================== MOTION CONTROL FUNCTIONS ====================

void stopBothDrives() {
    P1.writeAnalog(0, analogAControl);
    P1.writeAnalog(0, analogBControl);
    disableDriveA();
    disableDriveB();
}

void setForwardMotion() {
    enableDriveA();
    enableDriveB();
    P1.writeAnalog(medSpeed, analogAControl);
    P1.writeAnalog(medSpeed, analogBControl);
}

void setTurn(uint16_t leftSpeed, uint16_t rightSpeed) {
    // Set direction for each motor based on turn type verify on testing. 
    P1.writeDiscrete(LOW, directionAControl); // Forward
    P1.writeDiscrete(LOW, directionBControl); // Forward
    P1.writeAnalog(leftSpeed, analogAControl);
    P1.writeAnalog(rightSpeed, analogBControl);
}

// ==================== TURNING STRATEGIES ====================

void performStandardTurn() {
    // Both motors run, but at different speeds for gentle turn
    setTurn(lowSpeed, medSpeed);
}

void performSharpTurn() {
    // One motor stops/slows significantly for tight turn
    setTurn(0, medSpeed);
}

// ==================== LIGHT CONTROL FUNCTIONS ====================

void setStatusLights(bool systemOk) {
    if (systemOk) {
        P1.writeDiscrete(HIGH, greenSControl);
        P1.writeDiscrete(LOW, yellowSControl);
        P1.writeDiscrete(LOW, redSControl);
    } else {
        P1.writeDiscrete(LOW, greenSControl);
        P1.writeDiscrete(HIGH, yellowSControl);
        P1.writeDiscrete(LOW, redSControl);
    }
}

void setMotionLights(RobotState state) {
    // Reset all motion lights
    P1.writeDiscrete(LOW, redMControl);
    P1.writeDiscrete(LOW, yellowMControl);
    P1.writeDiscrete(LOW, greenMControl);
    
    switch(state) {
        case STOPPED:
            P1.writeDiscrete(HIGH, redMControl);
            break;
        case FORWARD:
            P1.writeDiscrete(HIGH, greenMControl);
            break;
        case TURNING:
            P1.writeDiscrete(HIGH, yellowMControl);
            break;
    }
}

// ==================== STATE MACHINE ====================

void handleRobotStateMachine() {
    // Check highest priority first - emergency stop
    if (isEmergencyStopActive()) {
        stopBothDrives();
        currentState = STOPPED;
        setMotionLights(currentState);
        return;
    }
    
    // Check if drives are ready
    bool drivesReady = areDrivesReady();
    setStatusLights(drivesReady);
    
    if (!drivesReady) {
        stopBothDrives();
        currentState = STOPPED;
        setMotionLights(currentState);
        return;
    }
    
    // Handle state transitions based on button inputs
    bool startPressed = P1.readDiscrete(startSignal);
    bool stopPressed = P1.readDiscrete(stopSignal);
    
    switch(currentState) {
        case STOPPED:
            if (startPressed) {
                currentState = FORWARD;
                setForwardMotion();
            }
            break;
            
        case FORWARD:
            if (stopPressed) {
                currentState = STOPPED;
                stopBothDrives();
            }
            
            break;
            
                
    }
    
    setMotionLights(currentState);
}
void handleTCPClient() {
    EthernetClient client = tcpServer.available();
    if (client) {
        Serial.println("Client connected");
        while (client.connected()) {
            if (client.available()) {
                String command = client.readStringUntil('\n');
                command.trim();
                Serial.print("Received command: ");
                Serial.println(command);
                // Command processing
                if (command.equalsIgnoreCase("START")) {
                    currentState = FORWARD;
                    setForwardMotion();
                    client.println("ACK: STARTED");
                } else if (command.equalsIgnoreCase("STOP")) {
                    stopBothDrives();
                    currentState = STOPPED;
                    client.println("ACK: STOPPED");
                } else if (command.equalsIgnoreCase("TURN")) {
                    performStandardTurn();
                    client.println("ACK: TURNING");
                } else if (command.equalsIgnoreCase("SHARP_TURN")) {
                    performSharpTurn();
                    client.println("ACK: SHARP TURN");
                } else if (command.equalsIgnoreCase("STATUS")) {
                    String statusMsg = (isEmergencyStopActive()) ? "EMERGENCY ACTIVE" : "ALL CLEAR";
                    client.println(statusMsg);
                } else {
                    client.println("NACK: Unknown command");
                }
            }
        }
        client.stop();
        Serial.println("Client disconnected");
    }
}

// ==================== SETUP AND MAIN LOOP ====================

void setup() {
    Serial.begin(115200);
    while (!P1.init()) {
        ; // Wait for Modules to Sign on
    }
// Initial startup check for I/O.. not sure if this code works well. DC
bool allLow = true; 
// Define warning messages as an array
const char* warningMessages[] = {
  "Enable signal is active at startup!",
  "Brake signal is active at startup!",
  "Direction signal is active at startup!",
  "Fault signal active at startup!",
  "Ready signal active at startup!"
};
// Define pin mappings as arrays
const channelLabel controlPins[] = {enableAControl, enableBControl, 
                                    brakeAControl, brakeBControl,
                                    directionAControl, directionBControl};
const channelLabel errorPins[] = {faultASignal, readyBSignal, faultASignal, readyBSignal};

// Read outputs and check for active signals
for (int i = 0; i < sizeof(controlPins) / sizeof(controlPins[0]); i++) {
  if (P1.readDiscrete(controlPins[i]) == HIGH) {
    Serial.println(warningMessages[i]);
  }
}

// Read inputs (error signals)
for (int i = 0; i < sizeof(errorPins) / sizeof(errorPins[0]); i++) {
  if (P1.readDiscrete(errorPins[i])) {
    Serial.println("Warning: " + String(warningMessages[sizeof(controlPins) / sizeof(controlPins[0]) + i]));
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
    // Initial safety check
    if (isEmergencyStopActive()) {
        Serial.println("EMERGENCY STOP ACTIVE - SYSTEM HALTED");
        setStatusLights(false);
    } else {
        Serial.println("System initialized - Ready for operation");
        setStatusLights(true);
    }
}

void loop() {
    unsigned long currentMillis = millis();

    // Periodically check for TCP clients
    if (currentMillis - lastCheck >= checkInterval) {
        lastCheck = currentMillis;
        handleTCPClient();
    }

    // Handle robot state machine
    handleRobotStateMachine();

    delay(50); 
}
