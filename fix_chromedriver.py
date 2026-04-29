import undetected_chromedriver as uc
import shutil
import os
import time

print("Downloading Mac chromedriver via undetected_chromedriver...")
try:
    options = uc.ChromeOptions()
    options.add_argument("--headless") # Headless so we don't open a visible browser window
    
    # Initialize uc.Chrome without driver_executable_path so it downloads the Mac native one
    driver = uc.Chrome(options=options)
    driver_path = driver.patcher.executable_path
    print(f"Downloaded driver path: {driver_path}")
    driver.quit()

    print("Copying Windows native binaries to project folder...")
    targets = ['chromedriver_fb.exe', 'chromedriver_ig.exe', 'chromedriver_th.exe', 'chromedriver_x.exe']
    for name in targets:
        target = os.path.abspath(os.path.join(os.getcwd(), name))
        shutil.copy(driver_path, target)
        print(f"Copied {target}")

    print("Successfully replaced drivers for Windows!")
except Exception as e:
    print(f"An error occurred: {e}")
