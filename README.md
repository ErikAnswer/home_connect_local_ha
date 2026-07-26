# home_connect_local_ha

The **home_connect_local_ha** allows users to integrate their home appliances supporting the [Home Connect](https://www.home-connect.com/global) standard for Bosch and Siemens using direct communication over the local network.

## Install the Integration

1. Go to the HACS -> Custom Repositories and add this repository as a Custom Repository [See HACS Documentation for help](https://hacs.xyz/docs/faq/custom_repositories/)

2. Click the button bellow and click 'Download' to install the Integration:

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=home_connect_local_ha&owner=ErikAnswer)

3. Restart Home Assistant.

## Prerequisites

To use this integration, you must first create a Home Connect account and connect your appliances.

## Setup

1. Use the [Home Connect Profile Downloader](https://github.com/bruestel/homeconnect-profile-downloader) to download your Appliance profiles, select "openHAB" as target. The downloaded ZIP-file contains each Appliance encryption Key and feature descriptions
2. Click the button below or use "Add Integration" in Home Assistant and select "home_connect_local_ha".

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homeconnect_ws)

3. Upload the downloaded Profile file.
4. Select the Appliance you want to setup.
5. When the initial connection to the Appliance fails, your asked to manually enter your Appliance IP-Address.
6. Repeat from Step 2 if you want to setup more than one Appliances.

### Configuration parameters

- Profile file: The Profile File you've downloaded with the [Home Connect Profile Downloader](https://github.com/bruestel/homeconnect-profile-downloader)
- Select Appliance: Select the Appliance you want to setup
- Host / IP-Address: Manually enter your Appliance Hostname or IP-Address

## Repairing Local Access

An appliance network reset can replace its local encryption key. When this
happens, the integration stops reconnecting and opens a reauthentication flow
instead of retrying the invalid key continuously.

The reauthentication flow always supports uploading a newly downloaded profile
ZIP. It also includes experimental cloud-assisted recovery:

1. Register an application in the [Home Connect Developer portal](https://developer.home-connect.com/).
2. Select **Authorization Code Grant Flow**.
3. Set the redirect URI to `https://my.home-assistant.io/redirect/oauth`.
4. Add the client ID and client secret under **Settings > Devices & services > Application credentials** in Home Assistant.
5. Select **Link Home Connect account** in the appliance reauthentication flow.

The local encryption profile is not part of the documented public Home Connect
API. If the account token cannot access it, the integration keeps the existing
configuration unchanged and asks for a profile ZIP.

## Remove integration

This integration follows standard integration removal, no extra steps are required.

## Reporting Issues and Bugs

### Bug report requirements

- A full debug log of at least reloading the config entry and any actions leading to an error
- The [Diagnostics](https://www.home-assistant.io/docs/configuration/troubleshooting/#download-diagnostics) of the Config Entry
- For reports relating to adding a new Appliance: the `*_DeviceDescription.xml` and `*_FeatureMapping.xml` files from the Profile File

### Enabling debug logging

Use one of these two methods enable debug logging:

- Through the UI:
  1. [Enable Debug logging](https://www.home-assistant.io/docs/configuration/troubleshooting) on the detail page of the integration
  2. Reload the config entry
  3. Perform the actions that lead to an error
  4. [Disable Debug logging](https://www.home-assistant.io/docs/configuration/troubleshooting/#disable-debug-logging-and-download-logs) on the detail page of the integration

- OR -

- Through configuration.yaml:
  1. Add the following to your [configuration.yaml](https://www.home-assistant.io/docs/configuration/) file:

     ```yaml
     logger:
     logs:
       custom_components.homeconnect_ws: debug # home_connect_local_ha Integration
       homeconnect_ws: debug
       homeconnect_websocket: debug # Homeconnect websocket Python package
     ```

  2. Restart Home Assistant
  3. Perform the actions that lead to an error
  4. Click the button below or navigate to "Settings" -> "Logs".

     [![Open your Home Assistant instance and show your Home Assistant logs.](https://my.home-assistant.io/badges/logs.svg)](https://my.home-assistant.io/redirect/logs/?)

  5. Download the log file using download button on the left
