# -*- coding: utf-8 -*-
#
# This code is free software; you can redistribute it and/or
# modify it under the terms of the GNU AFFERO GENERAL PUBLIC LICENSE
# License as published by the Free Software Foundation; either
# version 3 of the License, or any later version.
#
# This code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU AFFERO GENERAL PUBLIC LICENSE for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import logging
import time
import datetime
from privacyidea.lib.tokens.HMAC import HmacOtp
from privacyidea.lib.config import get_from_config
from privacyidea.lib.log import log_with
from privacyidea.lib.tokenclass import TokenClass
from privacyidea.lib.tokens.hotptoken import HotpTokenClass
from privacyidea.lib.decorators import check_token_locked
from privacyidea.lib.policy import ACTION, SCOPE, GROUP, Match
from privacyidea.lib.tokens.totptoken import TotpTokenClass
from privacyidea.lib.utils import determine_logged_in_userparams, parse_time_sec_int
from privacyidea.lib import _

log = logging.getLogger(__name__)


class DayPasswordTokenClass(TotpTokenClass):
    previous_otp_offset = 0

    desc_timestep = _('Specify the time step of the DayPassword token.')

    @log_with(log)
    def __init__(self, db_token):
        """
        Create a new day password token object from a DB Token object

        :param db_token: instance of the orm db object
        :type db_token:  orm object
        """
        TokenClass.__init__(self, db_token)
        self.set_type("daypassword")
        self.hKeyRequired = True

    @staticmethod
    def get_class_type():
        """
        return the token type shortname

        :return: 'daypassword'
        :rtype: string
        """
        return "daypassword"

    @staticmethod
    def get_class_prefix():
        """
        Return the prefix, that is used as a prefix for the serial numbers.

        :return: DayPasswordToken
        """
        return "DayPassword"

    @staticmethod
    @log_with(log)
    def get_class_info(key=None, ret='all'):
        """
        returns a subtree of the token definition

        :param key: subsection identifier
        :type key: string
        :param ret: default return value, if nothing is found
        :type ret: user defined
        :return: subsection if key exists or user defined
        :rtype: dict or scalar
        """
        res = {'type': 'daypassword',
               'title': 'Time based Password',
               'description': _('DayPassword: A time-based token with a variable timestep and the possibility'
                                ' to use the otp more than ones.'),
               'user': ['enroll'],
               # This tokentype is enrollable in the UI for...
               'ui_enroll': ["admin", "user"],
               'policy': {
                   SCOPE.USER: {
                       'daypassword_timestep': {'type': 'str',
                                                'desc': DayPasswordTokenClass.desc_timestep},
                       'daypassword_hashlib': {'type': 'str',
                                               'value': ["sha1",
                                                         "sha256",
                                                         "sha512"],
                                               'desc': DayPasswordTokenClass.desc_hash_func},
                       'daypassword_otplen': {'type': 'int',
                                              'value': [6, 8],
                                              'desc': DayPasswordTokenClass.desc_otp_len},
                       'daypassword_force_server_generate': {'type': 'bool',
                                                             'desc': DayPasswordTokenClass.desc_key_gen},
                       '2step': {'type': 'str',
                                 'value': ['allow', 'force'],
                                 'desc': DayPasswordTokenClass.desc_two_step_user}
                   },
                   SCOPE.ADMIN: {
                       'daypassword_timestep': {'type': 'str',
                                                'desc': DayPasswordTokenClass.desc_timestep},
                       'daypassword_hashlib': {'type': 'str',
                                               'value': ["sha1",
                                                         "sha256",
                                                         "sha512"],
                                               'desc': DayPasswordTokenClass.desc_hash_func},
                       'daypassword_otplen': {'type': 'int',
                                              'value': [6, 8],
                                              'desc': DayPasswordTokenClass.desc_otp_len},
                       'daypassword_force_server_generate': {'type': 'bool',
                                                             'desc': DayPasswordTokenClass.desc_key_gen},
                       '2step': {'type': 'str',
                                 'value': ['allow', 'force'],
                                 'desc': DayPasswordTokenClass.desc_two_step_admin}
                   },
                   SCOPE.ENROLL: {
                       '2step_clientsize': {'type': 'int',
                                            'desc': _("The size of the OTP seed part contributed "
                                                      "by the client (in bytes)")},
                       '2step_serversize': {'type': 'int',
                                            'desc': _("The size of the OTP seed part "
                                                      "contributed by the server (in bytes)")},
                       '2step_difficulty': {'type': 'int',
                                            'desc': _("The difficulty factor used for the "
                                                      "OTP seed generation ""(should be at least "
                                                      "10000)")},
                       'daypassword_' + ACTION.FORCE_APP_PIN: {
                           'type': 'bool',
                           'desc': _('Enforce setting an app pin for the privacyIDEA '
                                     'Authenticator App')
                       },
                       ACTION.MAXTOKENUSER: {
                           'type': 'int',
                           'desc': _("The user may only have this maximum number of remote tokens assigned."),
                           'group': GROUP.TOKEN
                       },
                       ACTION.MAXACTIVETOKENUSER: {
                           'type': 'int',
                           'desc': _(
                               "The user may only have this maximum number of active remote tokens assigned."),
                           'group': GROUP.TOKEN
                       }

                   }
               },
               }
        if key:
            ret = res.get(key, {})
        else:
            if ret == 'all':
                ret = res

        return ret

    @log_with(log)
    def update(self, param, reset_failcount=True):
        """
        This is called during initialization of the token
        to add additional attributes to the token object.

        :param param: dict of initialization parameters
        :type param: dict

        :return: nothing
        """
        HotpTokenClass.update(self, param, reset_failcount=reset_failcount)

        timeStep = param.get("timeStep", self.timestep)
        timeShift = param.get("timeShift", self.timeshift)
        # we support various hashlib methods, but only on create
        # which is effectively set in the update
        hashlibStr = param.get("hashlib", self.hashlib)

        self.add_tokeninfo("timeShift", timeShift)
        self.add_tokeninfo("timeStep", timeStep)
        self.add_tokeninfo("hashlib", hashlibStr)

    @property
    def timestep(self):
        timeStepping = parse_time_sec_int(self.get_tokeninfo("timeStep") or
                                          (get_from_config("daypassword.timeStep")) or "1d")

        return timeStepping

    @property
    def hashlib(self):
        hashlibStr = self.get_tokeninfo("hashlib") or \
                     get_from_config("daypassword.hashlib", 'sha1')
        return hashlibStr

    @log_with(log)
    def check_otp_exist(self, otp, options=None, symetric=False,
                        inc_counter=True):
        """
        checks if the given password value is/are values of this very token at all.
        This is used to autoassign and to determine the serial number of
        a token.

        :param otp: the to be verified otp value
        :type otp: string
        :return: counter or -1 if otp does not exist
        :rtype:  int
        """
        options = options or {}
        res = self.check_otp(otp, options=options)

        if inc_counter and res >= 0:
            # As usually the counter is increased in lib.token.checkUserPass,
            # we need to do this manually here:
            self.inc_otp_counter(res)
        return res

    @check_token_locked
    def check_otp(self, anOtpVal, counter=None, options=None):
        """
        validate the token passwort against a given passwordvalue

        :param anOtpVal: the to be verified passwordvalue
        :type anOtpVal:  string
        :param counter: the counter state, that should be verified. For DayPasswordToken
        this is the unix system time (seconds) divided by 30/60
        :type counter: int
        :param options: the dict, which could contain token specific info
        :type options: dict
        :return: the counter or -1
        :rtype: int
        """
        otplen = int(self.token.otplen)
        options = options or {}
        secretHOtp = self.token.get_otpkey()
        oCount = self.get_otp_count()
        inow = int(time.time())

        initTime = int(options.get('initTime', -1))
        if initTime != -1:
            server_time = int(initTime)
        else:
            server_time = time.time() + self.timeshift

        # If we have a counter from the parameter list
        if not counter:
            # No counter, so we take the current token_time
            counter = self._time2counter(server_time,
                                         timeStepping=self.timestep)

        hmac2Otp = HmacOtp(secretHOtp,
                           counter,
                           otplen,
                           self.get_hashlib(self.hashlib))
        res = hmac2Otp.checkOtp(anOtpVal,
                                int(1),
                                symetric=False)

        if -1 == res:
            # _autosync: test if two consecutive otps have been provided
            res = self._autosync(hmac2Otp, anOtpVal)

        if res != -1:
            # on success, we have to save the last attempt
            self.set_otp_count(res)
            # We could also store it temporarily
            # self.auth_details["matched_otp_counter"] = res

            # here we calculate the new drift/shift between the server time
            # and the tokentime
            tokentime = self._counter2time(res, self.timestep)
            tokenDt = datetime.datetime.fromtimestamp(tokentime / 1.0)

            nowDt = datetime.datetime.fromtimestamp(inow / 1.0)

            lastauth = self._counter2time(oCount, self.timestep)
            lastauthDt = datetime.datetime.fromtimestamp(lastauth / 1.0)

            log.debug("last auth : {0!r}".format(lastauthDt))
            log.debug("tokentime : {0!r}".format(tokenDt))
            log.debug("now       : {0!r}".format(nowDt))
            log.debug("delta     : {0!r}".format((tokentime - inow)))

        return res

    @log_with(log)
    def _autosync(self, hmac2Otp, anOtpVal):
        """
        synchronize the token based on two otp values automatically.
        If the OTP is invalid, that OTP counter is stored.
        If an old OTP counter is stored, it is checked, if the new
        OTP value is the next value after this counter.

        internal method to realize the _autosync within the
        checkOtp method

        :param hmac2Otp: the hmac object (with reference to the token secret)
        :type hmac2Otp: hmac object
        :param anOtpVal: the actual otp value
        :type anOtpVal: string
        :return: counter or -1 if otp does not exist
        :rtype:  int
        """
        res = -1
        autosync = get_from_config("AutoResync", False, return_bool=True)
        # if _autosync is not enabled: do nothing
        if autosync is False:
            return res

        info = self.get_tokeninfo()
        syncWindow = self.get_sync_window()

        # check if the otpval is valid in the sync scope
        res = hmac2Otp.checkOtp(anOtpVal, syncWindow, symetric=False)
        log.debug("found otpval {0!r} in syncwindow ({1!r}): {2!r}".format(anOtpVal, syncWindow, res))

        if res != -1:
            # if former is defined
            if "otp1c" in info:
                # check if this is consecutive
                otp1c = int(info.get("otp1c"))
                otp2c = res
                log.debug("otp1c: {0!r}, otp2c: {1!r}".format(otp1c, otp2c))
                if (otp1c + 1) != otp2c:
                    log.debug("Autoresync failed for token {0!s}. OTP values too far apart.".format(self.token.serial))
                    res = -1
                elif otp2c <= self.token.count:
                    # The resync was done with previous (old) OTP values
                    log.debug("Autoresync failed for token {0!s}. Previous OTP values used.".format(self.token.serial))
                    res = -1
                else:
                    log.info("Autoresync successful for token {0!s}.".format(self.token.serial))
                    server_time = time.time()
                    counter = int((server_time / self.timestep) + 0.5)

                    shift = otp2c - counter
                    info["timeShift"] = shift
                    self.set_tokeninfo(info)

                # now clean the resync data
                del info["otp1c"]
                self.set_tokeninfo(info)

            else:
                log.debug("setting otp1c: {0!s}".format(res))
                info["otp1c"] = res
                self.set_tokeninfo(info)
                res = -1

        return res

    def get_otp(self, current_time=None, do_truncation=True,
                time_seconds=None, challenge=None):
        """
        get the next OTP value

        :param current_time: the current time, for which the OTP value
        should be calculated for.
        :type current_time: datetime object
        :param time_seconds: the current time, for which the OTP value
        should be calculated for (date +%s)
        :type: time_seconds: int, unix system time seconds
        :return: next otp value, and PIN, if possible
        :rtype: tuple
        """
        otplen = int(self.token.otplen)
        secretHOtp = self.token.get_otpkey()

        hmac2Otp = HmacOtp(secretHOtp,
                           self.get_otp_count(),
                           otplen,
                           self.get_hashlib(self.hashlib))

        if time_seconds is None:
            time_seconds = time.time()
        if current_time:
            time_seconds = self._time2float(current_time)

        # we don't need to round here as we have already float
        counter = int(((time_seconds + self.timeshift) / self.timestep) + 0.5)
        otpval = hmac2Otp.generate(counter=counter,
                                   inc_counter=False,
                                   do_truncation=do_truncation,
                                   challenge=challenge)

        pin = self.token.get_pin()
        combined = "{0!s}{1!s}".format(otpval, pin)
        if get_from_config("PrependPin") == "True":
            combined = "{0!s}{1!s}".format(pin, otpval)

        return 1, pin, otpval, combined

    @log_with(log)
    def get_multi_otp(self, count=0, epoch_start=0, epoch_end=0,
                      curTime=None, timestamp=None):
        """
        return a dictionary of multiple future OTP values
        of the HOTP/HMAC token

        :param count: how many otp values should be returned
        :type count: int
        :param epoch_start: not implemented
        :param epoch_end: not implemented
        :param curTime: Simulate the servertime
        :type curTime: datetime
        :param timestamp: Simulate the servertime
        :type timestamp: epoch time
        :return: tuple of status: boolean, error: text and the OTP dictionary

        """
        otp_dict = {"type": "DayPasswordToken", "otp": {}}
        ret = False
        error = "No count specified"

        otplen = int(self.token.otplen)
        secretHOtp = self.token.get_otpkey()

        hmac2Otp = HmacOtp(secretHOtp, self.get_otp_count(),
                           otplen, self.get_hashlib(self.hashlib))

        if curTime:
            # datetime object provided for simulation
            tCounter = self._time2float(curTime)
        elif timestamp:
            # epoch time provided for simulation
            tCounter = int(timestamp)
        else:
            # use the current server time
            tCounter = self._time2float(datetime.datetime.now())

        # we don't need to round here as we have already float
        counter = int(((tCounter - self.timeshift) / self.timestep))

        otp_dict["shift"] = self.timeshift
        otp_dict["timeStepping"] = self.timeshift

        if count > 0:
            error = "OK"
            for i in range(0, count):
                otpval = hmac2Otp.generate(counter=counter + i,
                                           inc_counter=False)
                timeCounter = ((counter + i) * self.timestep) + self.timeshift

                val_time = datetime.datetime. \
                    fromtimestamp(timeCounter).strftime("%Y-%m-%d %H:%M:%S")
                otp_dict["otp"][counter + i] = {'otpval': otpval,
                                                'time': val_time}
            ret = True

        return ret, error, otp_dict

    @staticmethod
    def get_setting_type(key):
        settings = {"daypassword.hashlib": "public",
                    "daypassword.timeStep": "public"}
        return settings.get(key, "")

    @classmethod
    def get_default_settings(cls, g, params):
        """
        This method returns a dictionary with default settings for token
        enrollment.
        These default settings are defined in SCOPE.USER or SCOPE.ADMIN and are
        daypassword_hashlib, daypassword_timestep and daypassword_otplen.
        If these are set, the user or admin will only be able to enroll tokens
        with these values.

        The returned dictionary is added to the parameters of the API call.

        :param g: context object, see documentation of ``Match``
        :param params: The call parameters
        :type params: dict
        :return: default parameters
        """
        ret = {}
        if not g.logged_in_user:
            return ret
        (role, username, userrealm, adminuser, adminrealm) = determine_logged_in_userparams(g.logged_in_user,
                                                                                            params)
        hashlib_pol = Match.generic(g, scope=role,
                                    action="daypassword_hashlib",
                                    user=username,
                                    realm=userrealm,
                                    adminuser=adminuser,
                                    adminrealm=adminrealm).action_values(unique=True)
        if hashlib_pol:
            ret["hashlib"] = list(hashlib_pol)[0]

        timestep_pol = Match.generic(g, scope=role,
                                     action="daypassword_timestep",
                                     user=username,
                                     realm=userrealm,
                                     adminuser=adminuser,
                                     adminrealm=adminrealm).action_values(unique=True)
        if timestep_pol:
            ret["timeStep"] = list(timestep_pol)[0]

        otplen_pol = Match.generic(g, scope=role,
                                   action="daypassword_otplen",
                                   user=username,
                                   realm=userrealm,
                                   adminuser=adminuser,
                                   adminrealm=adminrealm).action_values(unique=True)
        if otplen_pol:
            ret["otplen"] = list(otplen_pol)[0]

        return ret

    @staticmethod
    def get_import_csv(l):
        """
        Read the list from a csv file and return a dictionary, that can be used
        to do a token_init.

        :param l: The list of the line of a csv file
        :type l: list
        :return: A dictionary of init params
        """
        params = TokenClass.get_import_csv(l)
        # timeStep
        if len(l) >= 5:
            params["timeStep"] = int(l[4].strip())
        else:
            params["timeStep"] = 30

        return params
