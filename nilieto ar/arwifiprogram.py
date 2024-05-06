import numpy as np
import argparse
import imutils
import sys
import cv2
import subprocess
import re
import platform

def get_wifi_info(os_name):
    wifi_info = {}

    # Function to parse Linux Wi-Fi information
    def parse_linux(output):
        #i made changes to the linux and windows functions
        #my device uses windows, and linux was similar.
        #mac will be changed if i have time for it.
        #separate lists of networks for the ones that are locked or not
        locked_networks = {}
        unlocked_networks = {}
        current_ssid = None
        for line in output.split('\n'):
            ssid_match = re.search(r'SSID: (.+)$', line)
            signal_match = re.search(r'signal: (-\d+) dBm', line)
            locked_match = re.search(r'Encryption\s+:\s(.+)', block)
            
            #see if there is some sort of encryption
            is_unlocked = False
            if locked_match:
                locked_match = locked_match.group(1)
                #searching for "None" exactly didn't work;
                #i assume some whitespace was involved
                if ("None") in locked_match:
                    is_unlocked = True

            if ssid_match and signal_match:
                rssi = int(signal_match.group(1))  # Assuming % as signal 'strength'
                rssi = (rssi / 2) - 100 # convert from percentage to dB from -100 to -50
                #check if there is encryption or not, and put it in the appropriate dictionary
                if locked_match and not is_unlocked:
                    locked_networks[ssid_match.group(1)] = rssi
                else:
                    unlocked_networks[ssid_match.group(1)] = rssi
        return locked_networks, unlocked_networks

    # Function to parse Mac Wi-Fi information
    def parse_mac(output):
        networks = {}
        for line in output.split('\n')[1:]:  # Skip the header line
            parts = line.strip().split()  # Remove leading spaces and split by whitespace
            if len(parts) >= 5:  # Ensure there are enough parts to include SSID, BSSID, etc.
                # The SSID could contain spaces, so we need to handle it specially
                # Since SSID can contain spaces and we assume it's at the beginning, we'll join all parts but the last five
                bssid = ' '.join(parts[:-5])  # Joining all parts except the last five assuming those are other metrics
                rssi = parts[-5]  # RSSI should now be the fifth last element, assuming fixed format
              
                # Validate and convert RSSI to integer
                try:
                    rssi_int = int(rssi)  # Convert RSSI to integer
                    # Check if BSSID is already in the dictionary, update if existing RSSI is weaker
                    if bssid not in networks or networks[bssid] < rssi_int:
                        networks[bssid] = rssi_int
                except ValueError:
                    # This can happen if RSSI is not a number, so we skip this line
                    continue
        return networks

    # Function to parse Windows Wi-Fi information
    def parse_windows(output):
        locked_networks = {}
        unlocked_networks = {}
        # Windows netsh command has a different output format
        for block in output.split('\n\n'):
            ssid_match = re.search(r'SSID\s+\d+\s+:\s(.+)', block)
            signal_match = re.search(r'Signal\s+:\s(\d+)%', block)
            locked_match = re.search(r'Encryption\s+:\s(.+)', block)
            
            is_unlocked = False
            if locked_match:
                locked_match = locked_match.group(1)
                if ("None") in locked_match:
                    is_unlocked = True

            if ssid_match and signal_match:
                rssi = int(signal_match.group(1))  # Assuming % as signal 'strength'
                rssi = (rssi / 2) - 100 # convert from percentage to dB from -100 to -50
                if locked_match and not is_unlocked:
                    
                    locked_networks[ssid_match.group(1)] = rssi
                else:
                    unlocked_networks[ssid_match.group(1)] = rssi
        return locked_networks, unlocked_networks

    if os_name.lower() == 'linux':
        result = subprocess.run(['nmcli', '-t', 'device', 'wifi', 'list'], capture_output=True, text=True)
        wifi_info = parse_linux(result.stdout)
    elif os_name.lower() == 'mac' or os_name.lower() == 'darwin' or os_name.lower() == 'macos':
        result = subprocess.run(['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-s'], capture_output=True, text=True)
        wifi_info = parse_mac(result.stdout)
    elif os_name.lower() == 'windows':
        result = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=Bssid'], capture_output=True, text=True, shell=True)
        wifi_info = parse_windows(result.stdout)
    else:
        raise ValueError("Unsupported operating system")

    return wifi_info

"""
Wi-fi strength examples and associated colors
-30 perfect (red 0, green 350)
-50 excellent
-60 good
-67 minimum for video (both 250)
-70 light browsing
-80 unstable
-90 unlikely (red 250, green 0)
"""

#this function puts the names of all the networks on the canvas.
def put_all_signals(canvas, width, height, locked_wifi_info, unlocked_wifi_info):
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    thickness = 2
    text_color = (255, 255, 255)
    #i want a gradient from red to green, so no blue.
    blue = 0
    #counters for iterating.
    current_locked = 0
    current_unlocked = 0
    #space the text evenly across the canvas
    x_spacing = int(width/2)
    #i want to find the denser vertical spacing and have both use that, just to look nice.
    if len(locked_wifi_info) != 0:
        someLocked = True
        y_spacing_locked = int(height/len(locked_wifi_info))
    if len(unlocked_wifi_info) != 0:
        someUnlocked = True
        y_spacing_unlocked = int(height/len(unlocked_wifi_info))
    if someLocked and someUnlocked:
        if y_spacing_locked < y_spacing_unlocked:
            y_spacing = y_spacing_locked
        else:
            y_spacing = y_spacing_unlocked
    
    #labels for the columns.
    #text stops getting cut off with a y-coordinate of 30.
    #and starting the signals at 60 stops them from overlapping.
    label_start = 30
    text_start = 60
    cv2.putText(canvas, "LOCKED", (0, label_start), font, font_scale, text_color, thickness)
    cv2.putText(canvas, "UNLOCKED", (x_spacing, label_start), font, font_scale, text_color, thickness)
    
    if someLocked:
        for signal, strength in locked_wifi_info.items():
            #dealing in postive values has been easier.
            pstrength = abs(strength)
            #decide colour
            if pstrength < 67:
                green = 250
                red = (pstrength-30)*6
            else:
                red = 250
                green = 250 - (pstrength-67)*10
            text_color = (blue, green, red)
            #decide placement
            text_x = 0
            text_y = y_spacing_locked*current_locked + text_start
            current_locked += 1
            text_size = cv2.getTextSize(signal, font, font_scale, thickness)[0]
            cv2.putText(canvas, signal, (text_x, text_y), font, font_scale, text_color, thickness)

    #same process as above, switching out some variables.
    if someUnlocked:
        for signal, strength in unlocked_wifi_info.items():
            pstrength = abs(strength)
            #decide colour
            if pstrength < 67:
                green = 250
                red = (pstrength-30)*6
            else:
                red = 250
                green = 250 - (pstrength-67)*10
            text_color = (blue, green, red)
            #decide placement
            text_x = x_spacing
            text_y = y_spacing_unlocked*current_unlocked + 60
            current_unlocked += 1
            text_size = cv2.getTextSize(signal, font, font_scale, thickness)[0]
            cv2.putText(canvas, signal, (text_x, text_y), font, font_scale, text_color, thickness)

def draw_canvas(width=640, height=480):
    # Create an empty canvas
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    #put the things there
    #start by generating our wifi lists
    os_name = platform.system()
    #sort them for easier comprehension
    locked_wifi_info, open_wifi_info = get_wifi_info(os_name)
    locked_wifi_info = dict(sorted(locked_wifi_info.items(), key=lambda item: item[1], reverse=True))
    unlocked_wifi_info = dict(sorted(open_wifi_info.items(), key=lambda item: item[1], reverse=True))
    #and call the function above to put the text on.
    put_all_signals(canvas, width, height, locked_wifi_info, unlocked_wifi_info)
    return canvas

cap = cv2.VideoCapture(0)
ret, image = cap.read()

# Initialize a dictionary to store the last known corners for each ArUco marker
cached_corners = {}

while True:
    source = draw_canvas()

    ret, image = cap.read()
    
    (imgH, imgW) = image.shape[:2]  
    
    print("[INFO] detecting markers...")
    arucoDict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_ORIGINAL)
    arucoParams = cv2.aruco.DetectorParameters()
    corners, ids, rejected = cv2.aruco.detectMarkers(image, arucoDict, parameters=arucoParams)

    cv2.aruco.drawDetectedMarkers(image, corners)
    
    # Update cached corners if new ones are found
    if ids is not None:
        for id_val, corner in zip(ids.flatten(), corners):
            cached_corners[id_val] = corner  # Update or add the corner for this ID
    
    # Check if we have all four required corners in the cache
    all_corners_found = all(id_val in cached_corners for id_val in [923, 1001, 241, 1007])
    
    if all_corners_found:
        # If all corners are found, update 'corners' to use the cached corners in order
        corners = [cached_corners[id_val] for id_val in [923, 1001, 241, 1007]]
        ids = np.array([923, 1001, 241, 1007]).reshape(-1, 1)  # Reshape for compatibility with later code
    else:
        print("[INFO] could not find 4 corners; found {}... press any key to continue or q to quit".format(len(cached_corners)))
        cv2.imshow("Input", image)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        continue
    
    # Construct augmented reality visualization only if all corners are found
    print("[INFO] constructing augmented reality visualization...")
    refPts = [np.squeeze(corner) for corner in corners]  # Flatten corner arrays
    
    # Define the *destination* transform matrix, ensuring points are in the correct order
    (refPtTL, refPtTR, refPtBR, refPtBL) = refPts
    dstMat = [refPtTL[0], refPtTR[1], refPtBR[2], refPtBL[3]]
    dstMat = np.array(dstMat)
    
    # grab the spatial dimensions of the source image and define the
    # transform matrix for the *source* image in top-left, top-right,
    # bottom-right, and bottom-left order
    (srcH, srcW) = source.shape[:2]
    srcMat = np.array([[0, 0], [srcW, 0], [srcW, srcH], [0, srcH]])
    # compute the homography matrix and then warp the source image to the
    # destination based on the homography
    (H, _) = cv2.findHomography(srcMat, dstMat)
    warped = cv2.warpPerspective(source, H, (imgW, imgH))

    # construct a mask for the source image now that the perspective warp
    # has taken place (we'll need this mask to copy the source image into
    # the destination)
    mask = np.zeros((imgH, imgW), dtype="uint8")
    cv2.fillConvexPoly(mask, dstMat.astype("int32"), (255, 255, 255),
        cv2.LINE_AA)
    # this step is optional, but to give the source image a black border
    # surrounding it when applied to the source image, you can apply a
    # dilation operation
    rect = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.dilate(mask, rect, iterations=2)
    # create a three channel version of the mask by stacking it depth-wise,
    # such that we can copy the warped source image into the input image
    maskScaled = mask.copy() / 255.0
    maskScaled = np.dstack([maskScaled] * 3)
    # copy the warped source image into the input image by (1) multiplying
    # the warped image and masked together, (2) multiplying the original
    # input image with the mask (giving more weight to the input where
    # there *ARE NOT* masked pixels), and (3) adding the resulting
    # multiplications together
    warpedMultiplied = cv2.multiply(warped.astype("float"), maskScaled)
    imageMultiplied = cv2.multiply(image.astype(float), 1.0 - maskScaled)
    output = cv2.add(warpedMultiplied, imageMultiplied)
    output = output.astype("uint8")    
    
    # show the source image, output of our augmented reality
    cv2.imshow("Input", image)
    cv2.imshow("Source", source)
    cv2.imshow("OpenCV AR Output", output)
    print("press any key to continue or q to quit")
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        sys.exit(0)
    else:
        continue

