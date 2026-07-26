"""Application credentials for Home Connect Local."""

from typing import TYPE_CHECKING

from homeassistant.components.application_credentials import AuthorizationServer

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

OAUTH2_AUTHORIZE = "https://api.home-connect.com/security/oauth/authorize"
OAUTH2_TOKEN = "https://api.home-connect.com/security/oauth/token"  # noqa: S105


async def async_get_authorization_server(
    hass: HomeAssistant,  # noqa: ARG001
) -> AuthorizationServer:
    """Return the Home Connect authorization server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )


async def async_get_description_placeholders(
    hass: HomeAssistant,  # noqa: ARG001
) -> dict[str, str]:
    """Return placeholders for the credentials dialog."""
    return {
        "developer_dashboard_url": "https://developer.home-connect.com/",
        "applications_url": "https://developer.home-connect.com/applications",
        "redirect_url": "https://my.home-assistant.io/redirect/oauth",
    }
