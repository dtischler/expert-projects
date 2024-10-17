# Edge Impulse - OpenMV FOMO Object Detection Example - Updated to print formatted object counts.
# Date: 2024-09-28. Author: Thomas Vikström.
# Modified to print the total object count and detailed counts without trailing comma.

import sensor, image, time, os, ml, math, uos, gc
from ulab import numpy as np

sensor.reset()                         # Reset and initialize the sensor.
sensor.set_pixformat(sensor.RGB565)    # Set pixel format to RGB565 (or GRAYSCALE)
sensor.set_framesize(sensor.QVGA)      # Set frame size to QVGA (320x240)
sensor.skip_frames(time=2000)          # Let the camera adjust.

net = None
labels = None
min_confidence = 0.5

try:
    # Load the model, alloc the model file on the heap if we have at least 64K free after loading.
    net = ml.Model("trained.tflite", load_to_fb=uos.stat('trained.tflite')[6] > (gc.mem_free() - (64*1024)))
except Exception as e:
    raise Exception('Failed to load "trained.tflite", did you copy the .tflite and labels.txt file onto the mass-storage device? (' + str(e) + ')')

try:
    labels = [line.rstrip('\n') for line in open("labels.txt")]
except Exception as e:
    raise Exception('Failed to load "labels.txt", did you copy the .tflite and labels.txt file onto the mass-storage device? (' + str(e) + ')')

colors = [ # Add more colors if you are detecting more than 7 types of classes at once.
    (255,   0,   0),
    (  0, 255,   0),
    (255, 255,   0),
    (  0,   0, 255),
    (255,   0, 255),
    (  0, 255, 255),
    (255, 255, 255),
]

threshold_list = [(math.ceil(min_confidence * 255), 255)]

def fomo_post_process(model, inputs, outputs):
    ob, oh, ow, oc = model.output_shape[0]

    x_scale = inputs[0].roi[2] / ow
    y_scale = inputs[0].roi[3] / oh

    scale = min(x_scale, y_scale)

    x_offset = ((inputs[0].roi[2] - (ow * scale)) / 2) + inputs[0].roi[0]
    y_offset = ((inputs[0].roi[3] - (ow * scale)) / 2) + inputs[0].roi[1]

    l = [[] for i in range(oc)]

    for i in range(oc):
        img = image.Image(outputs[0][0, :, :, i] * 255)
        blobs = img.find_blobs(
            threshold_list, x_stride=1, y_stride=1, area_threshold=1, pixels_threshold=1
        )
        for b in blobs:
            rect = b.rect()
            x, y, w, h = rect
            score = (
                img.get_statistics(thresholds=threshold_list, roi=rect).l_mean() / 255.0
            )
            x = int((x * scale) + x_offset)
            y = int((y * scale) + y_offset)
            w = int(w * scale)
            h = int(h * scale)
            l[i].append((x, y, w, h, score))
    return l

clock = time.clock()
while(True):
    clock.tick()

    img = sensor.snapshot()
    img.scale(x_scale=1.2, roi=(50, 55, 120, 240))

    # Apply lens correction if you need it.
    img.lens_corr()

    # Dictionary to store the count of each detected class in this frame.
    object_counts = {label: 0 for label in labels}

    for i, detection_list in enumerate(net.predict([img], callback=fomo_post_process)):
        if i == 0: continue  # Skip background class
        if len(detection_list) == 0: continue  # No detections for this class?

        object_counts[labels[i]] += len(detection_list)  # Update the count for this class

        for x, y, w, h, score in detection_list:
            center_x = math.floor(x + (w / 2))
            center_y = math.floor(y + (h / 2))
            img.draw_circle((center_x, center_y, 12), color=colors[i])

    # Calculate total object count
    total_count = sum(object_counts.values())

    # Construct formatted output string
    output_string = f"{total_count}, "  # Start with the total count
    object_details = [f"{label}: {count}" for label, count in object_counts.items() if count > 0]
    output_string += ", ".join(object_details)  # Join details without trailing comma

    # Print the final formatted string
    print(output_string)