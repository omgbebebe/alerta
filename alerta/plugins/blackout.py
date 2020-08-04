import logging

from alerta.exceptions import BlackoutPeriod
from alerta.plugins import PluginBase
from alerta.models.alert import Alert

LOG = logging.getLogger('alerta.plugins')


class BlackoutHandler(PluginBase):
    """
    Default suppression blackout handler will drop alerts that match a blackout
    period and will return a 202 Accept HTTP status code.

    If "NOTIFICATION_BLACKOUT" is set to ``True`` then the alert is processed
    but alert status is set to "blackout" and the alert will not be passed to
    any plugins for further notification.
    """

    def pre_receive(self, alert, **kwargs):
        NOTIFICATION_BLACKOUT = self.get_config('NOTIFICATION_BLACKOUT', default=True, type=bool, **kwargs)

        if self.get_config('ALARM_MODEL', **kwargs) == 'ALERTA':
            status = 'blackout'
        else:
            status = 'OOSRV'  # ISA_18_2

        if alert.is_blackout():
            if NOTIFICATION_BLACKOUT:
                LOG.debug('Set status to "{}" during blackout period (id={})'.format(status, alert.id))
                alert.status = status
            else:
                LOG.debug('Suppressed alert during blackout period (id={})'.format(alert.id))
                raise BlackoutPeriod('Suppressed alert during blackout period')
        return alert

    def post_receive(self, alert, **kwargs):
        return

    def status_change(self, alert, status, text, **kwargs):
        return

    def take_action(self, alert, action, text, **kwargs):
        raise NotImplementedError

    def delete(self, alert, **kwargs) -> bool:
        raise NotImplementedError

    def blackout_change(self, blackout, action):
        LOG.debug('Blackout {} state changed: {}'.format(blackout.id, action))
        alerts = Alert.find_all()
        for alert in alerts:
            if action == 'create' and alert.is_blackout():
                LOG.debug("{} alert should be muted".format(alert.id))
                attributes = alert.attributes
                attributes['blackout'] = blackout.id
                alert.update_attributes(attributes)
                alert.set_status('blackout', text='muted by blackout plugin')
            elif action == 'update':
                if alert.is_blackout():
                    if alert.status != 'blackout':
                        attributes = alert.attributes
                        attributes['blackout'] = blackout.id
                        alert.update_attributes(attributes)
                        alert.set_status('blackout', text='muted by blackout plugin')
                elif 'blackout' in alert.attributes:
                    alert.set_status('open', text='reopened by blackout plugin')
            elif action == 'delete':
                if 'blackout' in alert.attributes and alert.attributes['blackout'] == blackout.id:
                    alert.set_status('open', text='reopened by blackout plugin')
