# -*- coding: utf-8 -*-
#
# http://www.privacyidea.org
# (c) cornelius kölbel, privacyidea.org
#
# 2018-01-22 Cornelius Kölbel <cornelius.koelbel@netknights.it>
#            Add offline refill
# 2016-12-20 Cornelius Kölbel <cornelius.koelbel@netknights.it>
#            Add triggerchallenge endpoint
# 2016-10-23 Cornelius Kölbel <cornelius.koelbel@netknights.it>
#            Add subscription decorator
# 2016-09-05 Cornelius Kölbel <cornelius.koelbel@netknights.it>
#            SAML attributes on fail
# 2016-08-30 Cornelius Kölbel <cornelius.koelbel@netknights.it>
#            save client application type to database
# 2016-08-09 Cornelius Kölbel <cornelius@privacyidea.org>
#            Add possiblity to check OTP only
# 2015-11-19 Cornelius Kölbel <cornelius@privacyidea.org>
#            Add support for transaction_id to saml_check
# 2015-06-17 Cornelius Kölbel <cornelius@privacyidea.org>
#            Add policy decorator for API key requirement
# 2014-12-08 Cornelius Kölbel, <cornelius@privacyidea.org>
#            Complete rewrite during flask migration
#            Try to provide REST API
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

__doc__ = """This module contains the REST API for doing authentication.
The methods are tested in the file tests/test_api_validate.py

Authentication is either done by providing a username and a password or a
serial number and a password.

**Authentication workflow**

Authentication workflow is like this:

In case of authenticating a user:

 * :func:`privacyidea.lib.token.check_user_pass`
 * :func:`privacyidea.lib.token.check_token_list`
 * :func:`privacyidea.lib.tokenclass.TokenClass.authenticate`
 * :func:`privacyidea.lib.tokenclass.TokenClass.check_pin`
 * :func:`privacyidea.lib.tokenclass.TokenClass.check_otp`

In case if authenitcating a serial number:

 * :func:`privacyidea.lib.token.check_serial_pass`
 * :func:`privacyidea.lib.token.check_token_list`
 * :func:`privacyidea.lib.tokenclass.TokenClass.authenticate`
 * :func:`privacyidea.lib.tokenclass.TokenClass.check_pin`
 * :func:`privacyidea.lib.tokenclass.TokenClass.check_otp`

"""
from flask import (Blueprint, request, g, current_app)
from privacyidea.lib.user import get_user_from_param, log_used_user
from .lib.utils import send_result, getParam
from ..lib.decorators import (check_user_or_serial_in_request)
from .lib.utils import required
from privacyidea.lib.error import ParameterError
from privacyidea.lib.token import (check_user_pass, check_serial_pass,
                                   check_otp, create_challenges_from_tokens, get_one_token)
from privacyidea.api.lib.utils import get_all_params
from privacyidea.lib.config import (return_saml_attributes, get_from_config,
                                    return_saml_attributes_on_fail,
                                    SYSCONF, ensure_no_config_object)
from privacyidea.lib.audit import getAudit
from privacyidea.api.lib.prepolicy import (prepolicy, set_realm,
                                           api_key_required, mangle,
                                           save_client_application_type,
                                           check_base_action, pushtoken_wait)
from privacyidea.api.lib.postpolicy import (postpolicy,
                                            check_tokentype, check_serial,
                                            check_tokeninfo,
                                            no_detail_on_fail,
                                            no_detail_on_success, autoassign,
                                            offline_info,
                                            add_user_detail_to_response, construct_radius_response,
                                            mangle_challenge_response)
from privacyidea.lib.policy import PolicyClass
from privacyidea.lib.event import EventConfiguration
import logging
from privacyidea.api.register import register_blueprint
from privacyidea.api.recover import recover_blueprint
from privacyidea.lib.utils import get_client_ip
from privacyidea.lib.event import event
from privacyidea.lib.challenge import get_challenges, extract_answered_challenges
from privacyidea.lib.subscriptions import CheckSubscription
from privacyidea.api.auth import admin_required
from privacyidea.lib.policy import ACTION
from privacyidea.lib.token import get_tokens
from privacyidea.lib.machine import list_token_machines
from privacyidea.lib.applications.offline import MachineApplication
import json

log = logging.getLogger(__name__)

validate_blueprint = Blueprint('validate_blueprint', __name__)


@validate_blueprint.before_request
@register_blueprint.before_request
@recover_blueprint.before_request
def before_request():
    """
    This is executed before the request
    """
    ensure_no_config_object()
    request.all_data = get_all_params(request.values, request.data)
    request.User = get_user_from_param(request.all_data)
    privacyidea_server = current_app.config.get("PI_AUDIT_SERVERNAME") or \
                         request.host
    # Create a policy_object, that reads the database audit settings
    # and contains the complete policy definition during the request.
    # This audit_object can be used in the postpolicy and prepolicy and it
    # can be passed to the innerpolicies.

    g.policy_object = PolicyClass()

    g.audit_object = getAudit(current_app.config)
    g.event_config = EventConfiguration()
    # access_route contains the ip addresses of all clients, hops and proxies.
    g.client_ip = get_client_ip(request, get_from_config(SYSCONF.OVERRIDECLIENT))
    # Save the HTTP header in the localproxy object
    g.request_headers = request.headers
    g.audit_object.log({"success": False,
                        "action_detail": "",
                        "client": g.client_ip,
                        "client_user_agent": request.user_agent.browser,
                        "privacyidea_server": privacyidea_server,
                        "action": "{0!s} {1!s}".format(request.method, request.url_rule),
                        "info": ""})


@validate_blueprint.route('/offlinerefill', methods=['POST'])
@check_user_or_serial_in_request(request)
@event("validate_offlinerefill", request, g)
def offlinerefill():
    """
    This endpoint allows to fetch new offline OTP values for a token,
    that is already offline.
    According to the definition it will send the missing OTP values, so that
    the client will have as much otp values as defined.

    :param serial: The serial number of the token, that should be refilled.
    :param refilltoken: The authorization token, that allows refilling.
    :param pass: the last password (maybe password+OTP) entered by the user
    :return:
    """
    serial = getParam(request.all_data, "serial", required)
    refilltoken = getParam(request.all_data, "refilltoken", required)
    password = getParam(request.all_data, "pass", required)
    tokenobj_list = get_tokens(serial=serial)
    if len(tokenobj_list) != 1:
        raise ParameterError("The token does not exist")
    else:
        tokenobj = tokenobj_list[0]
        machine_defs = list_token_machines(serial)
        # check if is still an offline token:
        for mdef in machine_defs:
            if mdef.get("application") == "offline":
                # check refill token:
                if tokenobj.get_tokeninfo("refilltoken") == refilltoken:
                    # refill
                    otps = MachineApplication.get_refill(tokenobj, password, mdef.get("options"))
                    refilltoken = MachineApplication.generate_new_refilltoken(tokenobj)
                    response = send_result(True)
                    content = response.json
                    content["auth_items"] = {"offline": [{"refilltoken": refilltoken,
                                                          "response": otps}]}
                    response.set_data(json.dumps(content))
                    return response
        raise ParameterError("Token is not an offline token or refill token is incorrect")


@validate_blueprint.route('/check', methods=['POST', 'GET'])
@validate_blueprint.route('/radiuscheck', methods=['POST', 'GET'])
@postpolicy(mangle_challenge_response, request=request)
@postpolicy(construct_radius_response, request=request)
@postpolicy(no_detail_on_fail, request=request)
@postpolicy(no_detail_on_success, request=request)
@postpolicy(add_user_detail_to_response, request=request)
@postpolicy(offline_info, request=request)
@postpolicy(check_tokeninfo, request=request)
@postpolicy(check_tokentype, request=request)
@postpolicy(check_serial, request=request)
@postpolicy(autoassign, request=request)
@prepolicy(pushtoken_wait, request=request)
@prepolicy(set_realm, request=request)
@prepolicy(mangle, request=request)
@prepolicy(save_client_application_type, request=request)
@check_user_or_serial_in_request(request)
@CheckSubscription(request)
@prepolicy(api_key_required, request=request)
@event("validate_check", request, g)
def check():
    """
    check the authentication for a user or a serial number.
    Either a ``serial`` or a ``user`` is required to authenticate.
    The PIN and OTP value is sent in the parameter ``pass``.
    In case of successful authentication it returns ``result->value: true``.

    In case of a challenge response authentication a parameter ``exception=1``
    can be passed. This would result in a HTTP 500 Server Error response if
    an error occurred during sending of SMS or Email.

    In case ``/validate/radiuscheck`` is requested, the responses are
    modified as follows: A successful authentication returns an empty HTTP
    204 response. An unsuccessful authentication returns an empty HTTP
    400 response. Error responses are the same responses as for the
    ``/validate/check`` endpoint.

    :param serial: The serial number of the token, that tries to authenticate.
    :param user: The loginname/username of the user, who tries to authenticate.
    :param realm: The realm of the user, who tries to authenticate. If the
        realm is omitted, the user is looked up in the default realm.
    :param pass: The password, that consists of the OTP PIN and the OTP value.
    :param otponly: If set to 1, only the OTP value is verified. This is used
        in the management UI. Only used with the parameter serial.
    :param transaction_id: The transaction ID for a response to a challenge
        request
    :param state: The state ID for a response to a challenge request

    :return: a json result with a boolean "result": true

    **Example Validation Request**:

        .. sourcecode:: http

           POST /validate/check HTTP/1.1
           Host: example.com
           Accept: application/json

           user=user
           realm=realm1
           pass=s3cret123456

    **Example response** for a successful authentication:

       .. sourcecode:: http

           HTTP/1.1 200 OK
           Content-Type: application/json

            {
              "detail": {
                "message": "matching 1 tokens",
                "serial": "PISP0000AB00",
                "type": "spass"
              },
              "id": 1,
              "jsonrpc": "2.0",
              "result": {
                "status": true,
                "value": true
              },
              "version": "privacyIDEA unknown"
            }

    **Example response** for this first part of a challenge response
    authentication:

       .. sourcecode:: http

           HTTP/1.1 200 OK
           Content-Type: application/json

            {
              "detail": {
                "serial": "PIEM0000AB00",
                "type": "email",
                "transaction_id": "12345678901234567890",
                "multi_challenge: [ {"serial": "PIEM0000AB00",
                                     "transaction_id":  "12345678901234567890",
                                     "message": "Please enter otp from your
                                     email"},
                                    {"serial": "PISM12345678",
                                     "transaction_id": "12345678901234567890",
                                     "message": "Please enter otp from your
                                     SMS"}
                ]
              },
              "id": 1,
              "jsonrpc": "2.0",
              "result": {
                "status": true,
                "value": false
              },
              "version": "privacyIDEA unknown"
            }

    In this example two challenges are triggered, one with an email and one
    with an SMS. The application and thus the user has to decide, which one
    to use. They can use either.

    .. note:: All challenge response tokens have the same transaction_id in
       this case.
    """
    user = request.User
    serial = getParam(request.all_data, "serial")
    password = getParam(request.all_data, "pass", required)
    otp_only = getParam(request.all_data, "otponly")
    options = {"g": g,
               "clientip": g.client_ip}
    # Add all params to the options
    for key, value in request.all_data.items():
            if value and key not in ["g", "clientip"]:
                options[key] = value

    g.audit_object.log({"user": user.login,
                        "resolver": user.resolver,
                        "realm": user.realm})

    if serial:
        if user:
            # check if the given token belongs to the user
            if not get_tokens(user=user, serial=serial, count=True):
                raise ParameterError('Given serial does not belong to given user!')
        if not otp_only:
            result, details = check_serial_pass(serial, password, options=options)
        else:
            result, details = check_otp(serial, password)

    else:
        result, details = check_user_pass(user, password, options=options)

    g.audit_object.log({"info": log_used_user(user, details.get("message")),
                        "success": result,
                        "serial": serial or details.get("serial"),
                        "token_type": details.get("type")})
    return send_result(result, details=details)


@validate_blueprint.route('/samlcheck', methods=['POST', 'GET'])
@postpolicy(no_detail_on_fail, request=request)
@postpolicy(no_detail_on_success, request=request)
@postpolicy(add_user_detail_to_response, request=request)
@postpolicy(check_tokeninfo, request=request)
@postpolicy(check_tokentype, request=request)
@postpolicy(check_serial, request=request)
@postpolicy(autoassign, request=request)
@prepolicy(pushtoken_wait, request=request)
@prepolicy(set_realm, request=request)
@prepolicy(mangle, request=request)
@prepolicy(save_client_application_type, request=request)
@check_user_or_serial_in_request(request)
@CheckSubscription(request)
@prepolicy(api_key_required, request=request)
@event("validate_check", request, g)
def samlcheck():
    """
    Authenticate the user and return the SAML user information.

    :param user: The loginname/username of the user, who tries to authenticate.
    :param realm: The realm of the user, who tries to authenticate. If the
        realm is omitted, the user is looked up in the default realm.
    :param pass: The password, that consists of the OTP PIN and the OTP value.

    :return: a json result with a boolean "result": true

    **Example response** for a successful authentication:

       .. sourcecode:: http

           HTTP/1.1 200 OK
           Content-Type: application/json

            {
              "detail": {
                "message": "matching 1 tokens",
                "serial": "PISP0000AB00",
                "type": "spass"
              },
              "id": 1,
              "jsonrpc": "2.0",
              "result": {
                "status": true,
                "value": {"attributes": {
                            "username": "koelbel",
                            "realm": "themis",
                            "mobile": null,
                            "phone": null,
                            "myOwn": "/data/file/home/koelbel",
                            "resolver": "themis",
                            "surname": "Kölbel",
                            "givenname": "Cornelius",
                            "email": null},
                          "auth": true}
              },
              "version": "privacyIDEA unknown"
            }

    The response in value->attributes can contain additional attributes
    (like "myOwn") which you can define in the LDAP resolver in the attribute
    mapping.
    """
    user = request.User
    password = getParam(request.all_data, "pass", required)
    options = {"g": g,
               "clientip": g.client_ip}
    # Add all params to the options
    for key, value in request.all_data.items():
            if value and key not in ["g", "clientip"]:
                options[key] = value

    auth, details = check_user_pass(user, password, options=options)
    ui = user.info
    result_obj = {"auth": auth,
                  "attributes": {}}
    if return_saml_attributes():
        if auth or return_saml_attributes_on_fail():
            # privacyIDEA's own attribute map
            result_obj["attributes"] = {"username": ui.get("username"),
                                        "realm": user.realm,
                                        "resolver": user.resolver,
                                        "email": ui.get("email"),
                                        "surname": ui.get("surname"),
                                        "givenname": ui.get("givenname"),
                                        "mobile": ui.get("mobile"),
                                        "phone": ui.get("phone")
                                        }
            # additional attributes
            for k, v in ui.items():
                result_obj["attributes"][k] = v

    g.audit_object.log({"info": log_used_user(user, details.get("message")),
                        "success": auth,
                        "serial": details.get("serial"),
                        "token_type": details.get("type"),
                        "user": user.login,
                        "resolver": user.resolver,
                        "realm": user.realm})
    return send_result(result_obj, details=details)


@validate_blueprint.route('/triggerchallenge', methods=['POST', 'GET'])
@admin_required
@postpolicy(mangle_challenge_response, request=request)
@check_user_or_serial_in_request(request)
@prepolicy(check_base_action, request, action=ACTION.TRIGGERCHALLENGE)
@event("validate_triggerchallenge", request, g)
def trigger_challenge():
    """
    An administrator can call this endpoint if he has the right of
    ``triggerchallenge`` (scope: admin).
    He can pass a ``user`` name and or a ``serial`` number.
    privacyIDEA will trigger challenges for all native challenges response
    tokens, possessed by this user or only for the given serial number.

    The request needs to contain a valid PI-Authorization header.

    :param user: The loginname/username of the user, who tries to authenticate.
    :param realm: The realm of the user, who tries to authenticate. If the
        realm is omitted, the user is looked up in the default realm.
    :param serial: The serial number of the token.

    :return: a json result with a "result" of the number of matching
        challenge response tokens

    **Example response** for a successful triggering of challenge:

       .. sourcecode:: http

           {"jsonrpc": "2.0",
            "signature": "1939...146964",
            "detail": {"transaction_ids": ["03921966357577766962"],
                       "messages": ["Enter the OTP from the SMS:"],
                       "threadid": 140422378276608},
            "versionnumber": "unknown",
            "version": "privacyIDEA unknown",
            "result": {"status": true,
                       "value": 1},
            "time": 1482223663.517212,
            "id": 1}

    **Example response** for response, if the user has no challenge token:

       .. sourcecode:: http

           {"detail": {"messages": [],
                       "threadid": 140031212377856,
                       "transaction_ids": []},
            "id": 1,
            "jsonrpc": "2.0",
            "result": {"status": true,
                       "value": 0},
            "signature": "205530282...54508",
            "time": 1484303812.346576,
            "version": "privacyIDEA 2.17",
            "versionnumber": "2.17"}

    **Example response** for a failed triggering of a challenge. In this case
        the ``status`` will be ``false``.

       .. sourcecode:: http

           {"detail": null,
            "id": 1,
            "jsonrpc": "2.0",
            "result": {"error": {"code": 905,
                                 "message": "ERR905: The user can not be
                                 found in any resolver in this realm!"},
                       "status": false},
            "signature": "14468...081555",
            "time": 1484303933.72481,
            "version": "privacyIDEA 2.17"}

    """
    user = request.User
    serial = getParam(request.all_data, "serial")
    details = {"messages": [],
               "transaction_ids": []}
    options = {"g": g,
               "clientip": g.client_ip,
               "user": user}

    token_objs = get_tokens(serial=serial, user=user, active=True, revoked=False, locked=False)
    # Only use the tokens, that are allowed to do challenge response
    chal_resp_tokens = [token_obj for token_obj in token_objs if "challenge" in token_obj.mode]
    create_challenges_from_tokens(chal_resp_tokens, details, options)
    result_obj = len(details.get("multi_challenge"))

    challenge_serials = [challenge_info["serial"] for challenge_info in details["multi_challenge"]]
    g.audit_object.log({
        "user": user.login,
        "resolver": user.resolver,
        "realm": user.realm,
        "success": result_obj > 0,
        "info": log_used_user(user, "triggered {0!s} challenges".format(result_obj)),
        "serial": ",".join(challenge_serials),
    })

    return send_result(result_obj, details=details)


@validate_blueprint.route('/polltransaction', methods=['GET'])
@validate_blueprint.route('/polltransaction/<transaction_id>', methods=['GET'])
@prepolicy(mangle, request=request)
@CheckSubscription(request)
@prepolicy(api_key_required, request=request)
def poll_transaction(transaction_id=None):
    """
    Given a mandatory transaction ID, check if any non-expired challenge for this transaction ID
    has been answered. In this case, return true. If this is not the case, return false.
    This endpoint also returns false if no challenge with the given transaction ID exists.

    This is mostly useful for out-of-band tokens that should poll this endpoint
    to determine when to send an authentication request to ``/validate/check``.

    :jsonparam transaction_id: a transaction ID
    """
    if transaction_id is None:
        transaction_id = getParam(request.all_data, "transaction_id", required)
    # Fetch a list of non-exired challenges with the given transaction ID
    # and determine whether it contains at least one non-expired answered challenge.
    matching_challenges = [challenge for challenge in get_challenges(transaction_id=transaction_id)
                           if challenge.is_valid()]
    answered_challenges = extract_answered_challenges(matching_challenges)

    if answered_challenges:
        result = True
        log_challenges = answered_challenges
    else:
        result = False
        log_challenges = matching_challenges

    # We now determine the information that should be written to the audit log:
    # * If there are no answered valid challenges, we log all token serials of challenges matching
    #   the transaction ID and the corresponding token owner
    # * If there are any answered valid challenges, we log their token serials and the corresponding user
    if log_challenges:
        g.audit_object.log({
            "serial": ",".join(challenge.serial for challenge in log_challenges),
        })
        # The token owner should be the same for all matching transactions
        user = get_one_token(serial=log_challenges[0].serial).user
        if user:
            g.audit_object.log({
                "user": user.login,
                "resolver": user.resolver,
                "realm": user.realm,
            })

    # In any case, we log the transaction ID
    g.audit_object.log({
        "info": u"transaction_id: {}".format(transaction_id),
        "success": result
    })

    return send_result(result)
