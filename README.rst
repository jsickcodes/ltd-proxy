#########
ltd-proxy
#########

LTD Proxy is a secure front-end proxy for LTD projects that are hosted on Amazon AWS.
It uses GitHub OAuth to authenticate visitors and GitHub organization and/or team memberships to authorize access to pages at specific URL path prefixes.

Kubernetes deployment
=====================

Secret resource
---------------

Besides the ConfigMaps, your kustomized deployment needs to include a secret resource that is referenced as environment variables from the deployment's ``app`` container.
This secret could be generated from a Vault secret or an AWS Secret, or could be a plain Kubernetes Secret, such as:

.. code-block:: yaml

   apiVersion: v1
   kind: Secret
   type: Opaque
   metadata:
     name: ltdproxy
   data:
     LTDPROXY_AWS_ACCESS_KEY_ID: ...
     LTDPROXY_AWS_SECRET_ACCESS_KEY: ...
     LTDPROXY_GITHUB_OAUTH_ID: ...
     LTDPROXY_GITHUB_OAUTH_SECRET: ...
     LTDPROXY_SESSION_KEY: ...
