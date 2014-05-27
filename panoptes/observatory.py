#!/usr/env/python

from __future__ import division, print_function

# Import General Tools
import sys
import os
import argparse

import ephem
import datetime
import time

import importlib

# from panoptes import Panoptes
import panoptes
import panoptes.mount as mount
import panoptes.camera as camera
import panoptes.weather as weather

import panoptes.utils.logger as logger
import panoptes.utils.config as config
import panoptes.utils.error as error

@logger.has_logger
@config.has_config
class Observatory():

    """
    Main Observatory class
    """

    def __init__(self):
        """
        Starts up the observatory. Reads config file (TODO), sets up location,
        dates, mount, cameras, and weather station
        """

        self.logger.info('Initializing panoptes observatory')

        # Create default mount and cameras. Should be read in by config file
        self.mount = self.create_mount()
        # self.cameras = [self.create_camera(), self.create_camera()]
        # self.weather_station = self.create_weather_station()

        self.site = self.setup_site()

        # Static Initializations
        self.site.date = ephem.now()
        self.sun = ephem.Sun()        

        # State method mapper
        self.states = {
            'shutdown': self.while_shutdown,
            'sleeping': self.while_sleeping,
            'getting ready': self.while_getting_ready,
            'scheduling': self.while_scheduling,
            'slewing': self.while_slewing,
            'taking test image': self.while_taking_test_image,
            'analyzing': self.while_analyzing,
            'imaging': self.while_imaging,
            'parking': self.while_parking,
            'parked': self.while_parked,
        }

        # assume we are in shutdown on program startup
        self.current_state = 'shutdown'

    def setup_site(self, start_date=ephem.now()):
        site = ephem.Observer()

        if 'site' in self.config:
            config_site = self.config.get('site')

            site.lat = config_site.get('lat')
            site.lon = config_site.get('lon')
            site.elevation = float(config_site.get('elevation'))
            site.horizon = config_site.get('horizon')
        else:
            # Hilo, HI
            site.lat = '19:32:09.3876'
            site.lon = '-155:34:34.3164'
            site.elevation = float(3400)
            site.horizon = '-12'

        # Pressure initially set to 0.  This could be updated later.
        site.pressure = float(680)

        # Static Initializations
        site.date = start_date

        return site

    def create_mount(self, mount_info=None):
        """
        This will create a mount object
        """
        if mount_info is None:
            mount_info = self.config.get('mount')

        brand = mount_info['class']

        # Make sure there is a yaml config file for this mount brand

        self.logger.info('Creating mount: {}'.format(brand))

        m = None

        # Actually import the brand of mount
        try:
            module = importlib.import_module('.{}'.format(brand), 'panoptes.mount')
        except ImportError as err:
            raise error.NotFound(brand)

        m = module.Mount(port)

        return m

    def create_camera(self, brand='rebel'):
        """
        This will create a camera object
        """
        self.logger.info('Creating camera: {}'.format(brand))

        c = None

        # Actually import the brand of camera
        try:
            module = importlib.import_module('.{}'.format(brand), 'panoptes.camera')
            c = module.Camera()
        except ImportError as err:
            raise error.NotFound(msg=brand)

        return c

    def create_weather_station(self):
        """
        This will create a weather station object
        """
        self.logger.info('Creating WeatherStation')
        return weather.WeatherStation( )

    def start_observing(self):
        """
        The main start method for the observatory-. Usually called from a driver program.
        Puts observatory into a loop
        """
        # Operations Loop
        while True:
            if self.current_state == 'stop_observing':
                break

            self.query_conditions()
            next_state = states[self.current_state]()
            self.current_state = next_state

    def get_state(self):
        """
        Simply returns current_state
        """
        return self.current_state

    def query_conditions(self):
        # populates observatory.weather.safe
        observatory.weather.check_conditions()
        # populates observatory.camera.connected
        observatory.camera.is_connected()
        observatory.camera.is_cooling()  # populates observatory.camera.cooling
        observatory.camera.is_cooled()  # populates observatory.camera.cooled
        # populates observatory.camera.exposing
        observatory.camera.is_exposing()
        # populates observatory.mount.connected
        observatory.mount.is_connected()
        observatory.mount.is_tracking()  # populates observatory.mount.tracking
        observatory.mount.is_slewing()  # populates observatory.mount.slewing
        observatory.mount.is_parked()  # populates observatory.mount.parked

    def heartbeat(self):
        """
        Touch a file each time signaling life
        """
        self.logger.debug('Touching heartbeat file')
        with open(self.heartbeat_filename, 'w') as fileobject:
            fileobject.write(str(datetime.datetime.now()) + "\n")

    def is_dark(self, dark_horizon=-12):
        """
        Need to calculate day/night for site
        Initial threshold 12 deg twilight
        self.site.date = datetime.datetime.now()
        """
        self.logger.debug('Calculating is_dark.')
        self.site.date = ephem.now()
        self.sun.compute(self.site)

        self.is_dark = self.sun.alt < dark_horizon
        return self.is_dark


    def while_shutdown(self):
        '''
        The shutdown state happens during the day, before components have been
        connected.

        From the shutdown state, you can go to sleeping.  This transition should be
        triggered by timing.  At a user configured time, the system will connect to
        components and start cooling the camera in preparation for observing.  This
        time checking should be built in to this while_shutdown function and trigger
        a change of state.

        In shutdown state:
        - it is:                day
        - camera connected:     no
        - camera cooling:       N/A
        - camera cooled:        N/A
        - camera exposing:      N/A
        - mount connected:      no
        - mount tracking:       N/A
        - mount slewing:        N/A
        - mount parked:         N/A
        - weather:              N/A
        - target chosen:        N/A
        - test image taken:     N/A
        - target completed:     N/A
        - analysis attempted:   N/A
        - analysis in progress: N/A
        - astrometry solved:    N/A
        - levels determined:    N/A

        Timeout Condition:  This state has a timeout built in as it will end at a
        given time each day.
        '''
        self.current_state = "shutdown"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        # Check if self is in a condition consistent with shutdown state.
        if not self.time_to_start() and not self.camera.connected and not self.mount.connected:
            # All conditions are met.  Wait for start time.
            wait_time = 60
            self.logger.info(
                "In shutdown state.  Waiting {} sec for dark.".format(wait_time))
            time.sleep(wait_time)
        # If conditions are not consistent with shutdown state, do something.
        else:
            if self.mount.connected:
                # Mount is connected when not expected to be.
                self.logger.warning(
                    "Mount is connected in shutdown state.  Disconnecting.")
                self.mount.disconnect()
            if self.camera.connected:
                # Camera is connected when not expected to be.
                self.logger.warning(
                    "Camera is connected in shutdown state.  Disconnecting.")
                self.camera.disconnect()
            if self.time_to_start():
                # It is past start time.  Transition to sleeping state by
                # connecting to camera and mount.
                self.logger.info(
                    "Connect to camera and mount.  Transition to sleeping.")
                self.current_state = "sleeping"
                try:
                    self.camera.connect()
                except:
                    # Failed to connect to camera
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to camera.  Parking.")
                    self.mount.park()
                try:
                    self.mount.connect()
                except:
                    # Failed to connect to mount
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to mount.  Parking.")
                    self.mount.park()
        return self.current_state

    def while_sleeping(self):
        '''
        The sleeping state happens during the day, after components have been
        connected, while we are waiting for darkness.

        From the sleeping state you can go to parking and getting ready.  Moving to
        parking state should be triggered by bad weather.  Moving to getting ready
        state should be triggered by timing.  At a user configured time (i.e. at
        the end of twilight), the system will go to getting ready.

        In sleeping state:
        - it is:                day
        - camera connected:     yes
        - camera cooling:       no
        - camera cooled:        N/A
        - camera exposing:      no
        - mount connected:      yes
        - mount tracking:       no
        - mount slewing:        no
        - mount parked:         yes
        - weather:              N/A
        - target chosen:        N/A
        - test image taken:     N/A
        - target completed:     N/A
        - analysis attempted:   N/A
        - analysis in progress: N/A
        - astrometry solved:    N/A
        - levels determined:    N/A

        Timeout Condition:  This state does not have a formal timeout, but should
        check to see if it is night as this state should not happen during night.
        '''
        self.current_state = "sleeping"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        # Check if self is in a condition consistent with sleeping state.
        if not self.is_dark() and \
            self.camera.connected and \
            not self.camera.cooling and \
            not self.camera.exposing and \
            self.mount.connected and \
            not self.mount.tracking and \
            not self.mount.slewing and \
            self.mount.parked:
                wait_time = 60
                self.logger.info(
                    "In sleeping state.  Waiting {} sec for dark.".format(wait_time))
                time.sleep(wait_time)
        # If conditions are not consistent with sleeping state, do something.
        else:
                # If camera is not connected, connect it.
            if not self.camera.connected:
                self.logger.warning("Camera is not connected.  Connecting.")
                try:
                    self.camera.connect()
                except:
                    # Failed to connect to camera
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to camera.  Parking.")
                    self.mount.park()
            # If camera is cooling, stop camera cooling.
            if self.camera.cooling:
                self.logger.warning("Camera is cooling.  Turning off cooler.")
                try:
                    self.camera.set_cooling(False)
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Camera not responding to set cooling.  Parking.")
                    self.mount.park()
            # If camera is exposing
            if self.camera.exposing:
                self.logger.warning("Camera is exposing.  Canceling exposure.")
                try:
                    self.camera.cancel_exposure()
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Camera not responding to cancel exposure.  Parking.")
                    self.mount.park()
            # If mount is not connected, connect it.
            if not self.mount.connected:
                self.logger.warning("Mount is not connected.  Connecting.")
                try:
                    self.mount.connect()
                except:
                    # Failed to connect to mount
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to mount.  Parking.")
                    self.mount.park()
            # If mount is tracking.
            if self.mount.tracking:
                self.logger.warning(
                    "Mount is tracking.  Turning off tracking.")
                try:
                    self.mount.set_tracking_rate(0, 0)
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Mount not responding to set tracking.  Parking.")
                    self.mount.park()
            # If mount is slewing.
            if self.mount.slewing:
                self.logger.warning("Mount is slewing.  Canceling slew.")
                try:
                    self.mount.cancel_slew()
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Mount not responding to cancel slew.  Parking.")
                    self.mount.park()
            # If mount is not parked, park it.
            if not self.mount.parked:
                self.current_state = "parking"
                self.logger.critical(
                    "Mount not parked in sleeping state.  Parking.")
                self.mount.park()
            # If it is time for operations, go to getting ready.
            if self.is_dark() and self.weather.safe:
                self.current_state = "getting ready"
                self.logger.info(
                    "Conditions are now dark, moving to getting ready state.")
                self.logger.info("Turning on camera cooler.")
                try:
                    self.camera.set_cooling(True)
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Camera not responding to set cooling.  Parking.")
                    self.mount.park()
        return self.current_state

    def while_getting_ready(self):
        '''
        The getting ready state happens while it is dark, it checks if we are ready
        to observe.

        From the getting ready state, you can go to parking and scheduling.

        In the getting ready state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        no
        - camera exposing:      no
        - mount connected:      yes
        - mount tracking:       no
        - mount slewing:        no
        - mount parked:         N/A
        - weather:              safe
        - target chosen:        no
        - test image taken:     N/A
        - target completed:     N/A
        - analysis attempted:   N/A
        - analysis in progress: N/A
        - astrometry solved:    N/A
        - levels determined:    N/A

        To transition to the scheduling state the camera must reach the cooled
        condition.

        Timeout Condition:  There should be a reasonable timeout on this state.  The
        timeout period should be set such that the camera can go from ambient to
        cooled within the timeout period.  The state should only timeout under
        extreme circumstances as the cooling process should monitor whether the
        target temperature is reachable and adjust the camera set point higher if
        needed and this may need time to iterate and settle down to operating temp.
        If a timeout occurs, the system should go to parking state.
        '''
        self.current_state = "getting ready"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        # Check if self is in condition consistent with getting ready state.
        if self.is_dark() and \
            self.camera.connected and \
            self.camera.cooling and \
            not self.camera.cooled and \
            not self.camera.exposing and \
            self.mount.connected and \
            not self.mount.tracking and \
            not self.mount.slewing and \
            not self.scheduler.target and \
            self.weather.safe:
                self.logger.debug(
                    "Conditions expected for getting ready state are met.")
                wait_time = 10
                self.logger.info(
                    "In getting ready state.  Waiting {} sec for components to be ready.".format(wait_time))
                time.sleep(wait_time)
        # If conditions are not consistent with sleeping state, do something.
        else:
                # If camera is not connected, connect it.
            if not self.camera.connected:
                self.logger.warning("Camera is not connected.  Connecting.")
                try:
                    self.camera.connect()
                except:
                    # Failed to connect to camera
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to camera.  Parking.")
                    self.mount.park()
            # If camera is not cooling, start cooling.
            if not self.camera.cooling:
                self.logger.warning(
                    "Camera is not cooling.  Turning on cooling.")
                try:
                    self.camera.set_cooling(True)
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Camera not responding to set cooling.  Parking.")
                    self.mount.park()
            # If camera is exposing, cancel exposure.
            if self.camera.exposing:
                self.logger.warning("Camera is exposing.  Canceling exposure.")
                try:
                    self.camera.cancel_exposure()
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Camera not responding to cancel exposure.  Parking.")
                    self.mount.park()
            # If camera is cooled, move to scheduling.
            if self.camera.cooled and self.weather.safe:
                self.logger.warning(
                    "Camera is not cooling.  Turning on cooling.")
                self.current_state = "scheduling"
                try:
                    scheduler.get_target()
                except:
                    self.current_state = "getting ready"
                    self.logger.warning(
                        "Scheduler failed to get a target.  Going back to getting ready state.")
            # If mount is not connected, connect it.
            if not self.mount.connected:
                self.logger.warning("Mount is not connected.  Connecting.")
                try:
                    self.mount.connect()
                except:
                    # Failed to connect to mount
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to mount.  Parking.")
                    self.mount.park()
            # If mount is tracking.
            if self.mount.tracking:
                self.logger.warning(
                    "Mount is tracking.  Turning off tracking.")
                try:
                    self.mount.set_tracking_rate(0, 0)
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Mount not responding to set tracking.  Parking.")
                    self.mount.park()
            # If mount is slewing.
            if self.mount.slewing:
                self.logger.warning("Mount is slewing.  Canceling slew.")
                try:
                    self.mount.cancel_slew()
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Mount not responding to cancel slew.  Parking.")
                    self.mount.park()
            # If scheduler has a target, clear it.
            if self.scheduler.target:
                self.logger.debug("Clearing target queue.")
                self.scheduler.target = None
            # If weather is unsafe, park.
            if not self.weather.safe:
                self.current_state = "parking"
                self.logger.info("Weather is bad.  Parking.")
                try:
                    self.mount.park()
                except:
                    self.current_state = "getting ready"
                    self.logger.critical("Unable to park during bad weather.")
        return self.current_state

    def while_scheduling(self):
        '''
        The scheduling state happens while it is dark after we have requested a
        target from the scheduler, but before the target has been returned.  This
        assumes that the scheduling happens in another thread.

        From the scheduling state you can go to the parking state and the
        slewing state.

        In the scheduling state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      no
        - mount connected:      yes
        - mount tracking:       no
        - mount slewing:        no
        - mount parked:         either
        - weather:              safe
        - target chosen:        no
        - test image taken:     N/A
        - target completed:     N/A
        - analysis attempted:   N/A
        - analysis in progress: N/A
        - astrometry solved:    N/A
        - levels determined:    N/A

        To transition to the slewing state, the target field must be populated, then
        the slew command is sent to the mount.

        This sets:
        - target chosen:        yes
        - test image taken:     no
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        Timeout Condition:  A reasonable timeout period for this state should be
        set.  Some advanced scheduling algorithms with many targets to consider may
        need a significant amount of time to schedule, but that reduces observing
        efficiency, so I think the timout for this state should be of order 10 sec.
        If a timeout occurs, the system should go to getting ready state.  This does
        allow a potential infinite loop scenario if scheduling is broken, because
        going to the getting ready state will usually just bouce the system back to
        scheduling, but this is okay because it does not endanger the system as it
        will still park on bad weather and at the end of the night.
        '''
        self.current_state = "scheduling"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        # Check if self is in a condition consistent with scheduling state.
        if self.is_dark() and \
            self.camera.connected and \
            self.camera.cooling and \
            self.camera.cooled and \
            not self.camera.exposing and \
            self.mount.connected and \
            not self.mount.slewing and \
            self.weather.safe:
            pass
        # If conditions are not consistent with scheduling state, do something.
        else:
            # If it is day, park.
            if not self.is_dark():
                self.current_state = "parking"
                self.logger.info("End of night.  Parking.")
                try:
                    self.mount.park()
                except:
                    self.current_state = "getting ready"
                    self.logger.critical("Unable to park during bad weather.")
            # If camera is not connected, connect it and go to getting ready.
            if not self.camera.connected:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Camera not connected.  Connecting and going to getting ready state.")
                try:
                    self.camera.connect()
                except:
                    # Failed to connect to camera
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to camera.  Parking.")
                    self.mount.park()
            # If camera is not cooling, start cooling and go to getting ready.
            if not self.camera.cooling:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Camera cooler is off.  Turning cooler on and going to getting ready state.")
                try:
                    self.camera.set_cooling(True)
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Camera not responding to set cooling.  Parking.")
                    self.mount.park()
            # If camera is not cooled, go to getting ready.
            if not self.camera.cooled:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Camera not finished cooling.  Going to getting ready state.")
            # If camera is exposing, cancel exposure.
            if self.camera.exposing:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Camera is exposing.  Canceling exposure and going to getting ready state.")
                try:
                    self.camera.cancel_exposure()
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Camera not responding to cancel exposure.  Parking.")
                    self.mount.park()
            # If mount is not connected, connect it.
            if not self.mount.connected:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Mount not connected.  Connecting and going to getting ready state.")
                try:
                    self.mount.connect()
                except:
                    # Failed to connect to mount
                    # Exit to parking state and log problem.
                    self.current_state = "parking"
                    self.logger.critical(
                        "Unable to connect to mount.  Parking.")
                    self.mount.park()
            # If mount is slewing.
            if self.mount.slewing:
                self.current_state = "getting ready"
                self.logger.warning(
                    "Mount is slewing.  Cancelling slew and going to getting ready state.")
                try:
                    self.mount.cancel_slew()
                except:
                    self.current_state = "parking"
                    self.logger.critical(
                        "Mount not responding to cancel slew.  Parking.")
                    self.mount.park()
            # If scheduling is complete
            if self.scheduler.target and self.weather.safe:
                self.logger.info(
                    "Target selected: {}".format(self.scheduler.target.name))
                self.current_state = "slewing"
                self.logger.info("Slewing telescope.")
                try:
                    self.mount.slew_to(target)
                except:
                    self.logger.critical(
                        "Slew failed.  Going to getting ready.")
                    self.current_state = "getting ready"
            # If weather is unsafe, park.
            if not self.weather.safe:
                self.current_state = "parking"
                self.logger.info("Weather is bad.  Parking.")
                try:
                    self.mount.park()
                except:
                    self.current_state = "getting ready"
                    self.logger.critical("Unable to park during bad weather.")
        return self.current_state

    def while_slewing(self):
        '''
        The slewing state happens while the system is slewing to a target position
        (note: this is distinct from the slew which happens on the way to the park
        position).

        From the slewing state, you can go to the parking state, the taking
        test image state, and the imaging state.

        In the slewing state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      no
        - mount connected:      yes
        - mount tracking:       no
        - mount slewing:        yes
        - mount parked:         no
        - weather:              safe
        - target chosen:        yes
        - test image taken:     either
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        To go to the taking test image state, the slew must complete and test image
        taken is no.

        To go to the imaging state, the slew must complete and the test image taken
        must be yes.

        Completion of the slew sets:
        - mount slewing:        no

        Timeout Condition:  There should be a reasonable timeout condition on the
        slew which allows for long slews with a lot of extra time for settling and
        other considerations which may vary between mounts.  If a timeout occurs,
        the system should go to getting ready state.
        '''
        self.current_state = "slewing"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        # Check if self is in a condition consistent with slewing state.
        if self.mount.connected and self.mount.slewing:
        # If conditions are not consistent with scheduling state, do something.
            pass
        else:
            # If mount is no longer slewing exit to proper state
            if not self.mount.slewing and self.weather.safe:
                if not target.test_image_taken:
                    self.current_state = "taking test image"
                    self.camera.take_image(test_image=True)
                else:
                    self.current_state = "imaging"
                    self.camera.take_image(test_image=False)
            # If weather is unsafe, park.
            if not self.weather.safe:
                self.current_state = "parking"
                self.logger.info("Weather is bad.  Parking.")
                try:
                    self.mount.park()
                except:
                    self.current_state = "getting ready"
                    self.logger.critical("Unable to park during bad weather.")

        return self.current_state

    def while_taking_test_image(self):
        '''
        The taking test image state happens after one makes a large (threshold
        controlled by a setting) slew.  The system takes a short image, plate solves
        it, then determines the pointing offset and commands a correcting slew.  One
        might also check the image background levels in this test image an use them
        to set the exposure time in the science image.

        Note:  One might argue that this is so similar to the imaging state that
        they should be merged in to one state, but I think this is a useful
        distinction to make as the settings for the test image will be different
        than a science image.  For example, for a given target, only one test image
        needs to be taken, where we probably want >1 science image.  Also, we can
        use a flag to turn off this operation.

        From the taking test image state, you can go to the parking state
        and the analyzing state.

        In the taking test image state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      yes
        - mount connected:      yes
        - mount tracking:       yes
        - mount slewing:        no
        - mount parked:         no
        - weather:              safe
        - target chosen:        yes
        - test image taken:     no
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        To move to the analyzing state, the image must complete:

        This sets:
        - test image taken:     yes

        Timeout Condition:  A reasonable timeout should be set which allows for a
        short exposure time, plus download time and some additional overhead.  If a
        timeout occurs, ... actually I'm not sure what should happen in this case.
        Going to getting ready state will also just wait for the image to finish, so
        nothing is gained relative to having no timeout.  This suggests that we DO
        need a method to cancel an exposure which is invoked in case of a timeout,
        which is something I had specifically hoped NOT to have to create.
        '''
        self.current_state = "taking test image"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state

    def while_analyzing(self):
        '''
        The analyzing state happens after one has taken an image or test image.  It
        always operates on the last image taken (whose file name should be stored
        in a variable somewhere).

        From the analyzing state, you can go to the parking state, the
        getting ready state, or the slewing state.

        In the analyzing state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      no
        - mount connected:      yes
        - mount tracking:       yes
        - mount slewing:        no
        - mount parked:         no
        - weather:              safe
        - target chosen:        yes
        - test image taken:     yes
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        If the analysis is successful, this sets:
        - analysis attempted:   yes
        - analysis in progress: yes
        - astrometry solved:    yes
        - levels determined:    yes

        As part of analysis step, the system compares the number of images taken of
        this target since it was chosen to the minimum number requested by scheduler
        (typically three).  If we have taken enough images of this target, we set
        target completed to yes, if not, we leave it at no.

        To move to the slewing state, target complete must be no and astrometry
        solved is yes.  The slew recenters the target based on the astrometric
        solution.

        To move to the getting ready state, the target completed must be yes.  After
        a brief stop in getting ready state (to check that all systems are still
        ok), we would presumably go back to scheduling.  The scheduler may choose to
        observe this target again.  The minimum number of images is just that, a
        minimum, it defines the smallest schedulable block.

        We need to discuss what happens when analysis fails.

        Timeout Condition:  A readonable timeout should be set.  If a timeout
        occurs, we should handle that identically to a failure of the analysis.
        '''
        self.current_state = "analyzing"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state

    def while_imaging(self):
        '''
        This state happens as the camera is exposing.

        From the imaging state, you can go to the parking statee and the analyzing
        state.

        Note: as we are currently envisioning the system operations, you can not
        cancel an exposure.  The logic behind this is that if we want to go to a
        parked state, then we don't care about the image and it is easy to simply
        tag an image header with information that the exposure was interrupted by
        a park operation, so we don't care if the data gets written to disk in this
        case.  This avoids the requirement of writing complicated exposure
        cancelling code in to each camera driver.

        As a result, if the system has to park during an
        exposure (i.e. if the weather goes bad), the camera will contine to expose.
        This means that there are cases when the camera is exposing, but you are not
        in the imaging state.  There are some edge cases we need to test (especially
        in the parking and parked states) to ensure that the camera exposure
        finishes before those states are left.

        When we enter this state, we must reset the following:
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        In the imaging state:
        - it is:                night
        - camera connected:     yes
        - camera cooling:       on
        - camera cooled:        yes
        - camera exposing:      yes
        - mount connected:      yes
        - mount tracking:       yes
        - mount slewing:        no
        - mount parked:         no
        - weather:              safe
        - target chosen:        yes
        - test image taken:     yes
        - target completed:     no
        - analysis attempted:   no
        - analysis in progress: no
        - astrometry solved:    no
        - levels determined:    no

        Timeout Condition:  A reasonable timeout should be set is based on the
        exposure time, plus download time and some additional overhead.  If a
        timeout occurs, ... actually I'm not sure what should happen in this case.
        Going to getting ready state will also just wait for the image to finish, so
        nothing is gained relative to having no timeout.  This suggests that we DO
        need a method to cancel an exposure which is invoked in case of a timeout,
        which is something I had specifically hoped NOT to have to create.
        '''
        self.current_state = "imaging"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state

    def while_parking(self):
        '''
        This is the state which is the emergency exit.  A park command has been
        issued to put the system in a safe state, but we have not yet reached the
        park position.

        From the parking state, one can only exit to the parked state.

        Timeout Condition:  There are two options I see for a timeout on the parking
        state.  The first is to not have a timeout simply because if a park has been
        commanded, then we should assume that it is critical to safety to park and
        nothing should interrupt a park command.  Alternatively, I can imagine
        wanting to resend the park command if the system does not reach park.  The
        downside to this is that we might end up in a repeating loop of issuing a
        park command to the mount over and over again in a situation where there is
        a physical obstruction to the park operation and this damages the motors.
        There might be a third alternative which is to limit the number of retries
        on the park command after timeouts.
        '''
        self.current_state = "parking"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state

    def while_parked(self):
        '''
        The parked state is where the system exists at night when not observing.
        During the day, we are at the physical parked position for the mount, but
        we would be in either the shutdown or sleeping state.

        From the parked state we can go to shutdown (i.e. when the night ends), or
        we can go to getting ready (i.e. it is still night, conditions are now safe,
        and we can return to operations).

        Timeout Condition:  There is a natural timeout to this state which occurs at
        the end of the night which causes a transition to the shutdown state.
        '''
        self.current_state = "parked"
        self.debug.info(
            "Entering {} while_state function.".format(self.current_state))
        return self.current_state
