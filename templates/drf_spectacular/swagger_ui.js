"use strict";

const swaggerSettings = {{ settings|safe }};
const schemaAuthNames = {{ schema_auth_names|safe }};
let schemaAuthFailed = false;
const plugins = [];

const reloadSchemaOnAuthChange = () => {
  return {
    statePlugins: {
      auth: {
        wrapActions: {
          authorizeOauth2:(ori) => (...args) => {
            schemaAuthFailed = false;
            setTimeout(() => ui.specActions.download());
            return ori(...args);
          },
          authorize: (ori) => (...args) => {
            schemaAuthFailed = false;
            setTimeout(() => ui.specActions.download());
            return ori(...args);
          },
          logout: (ori) => (...args) => {
            schemaAuthFailed = false;
            setTimeout(() => ui.specActions.download());
            return ori(...args);
          },
        },
      },
    },
  };
};

if (schemaAuthNames.length > 0) {
  plugins.push(reloadSchemaOnAuthChange);
}

const uiInitialized = () => {
  try {
    ui;
    return true;
  } catch {
    return false;
  }
};

const isSchemaUrl = (url) => {
  if (!uiInitialized()) {
    return false;
  }
  return url === new URL(ui.getConfigs().url, document.baseURI).href;
};

const responseInterceptor = (response, ...args) => {
  if (!response.ok && isSchemaUrl(response.url)) {
    console.warn("schema request received '" + response.status + "'. disabling credentials for schema till logout.");
    if (!schemaAuthFailed) {
      // only retry once to prevent endless loop.
      schemaAuthFailed = true;
      setTimeout(() => ui.specActions.download());
    }
  }

  // --- AUTO AUTHORIZE ON LOGIN / TOKEN GENERATION ---
  try {
    if (response.status >= 200 && response.status < 300) {
      let token = null;
      let bodyData = response.body;

      if (typeof bodyData === "string") {
        try {
          bodyData = JSON.parse(bodyData);
        } catch (e) {}
      }

      if (bodyData && typeof bodyData === "object") {
        if (bodyData.data && bodyData.data.access_token) {
          token = bodyData.data.access_token;
        } else if (bodyData.access_token) {
          token = bodyData.access_token;
        }
      }

      if (!token && response.text && typeof response.text === "string") {
        try {
          const parsed = JSON.parse(response.text);
          token = (parsed.data && parsed.data.access_token) || parsed.access_token;
        } catch (e) {}
      }

      if (token && typeof token === "string") {
        token = token.replace(/^Bearer\s+/i, "").trim();
        if (token.length > 10 && uiInitialized()) {
          ui.authActions.authorize({
            BearerAuth: {
              name: "BearerAuth",
              schema: {
                type: "http",
                scheme: "bearer",
                bearerFormat: "JWT"
              },
              value: token
            }
          });
          console.log("%c[Swagger UI] Auto-Authorized with Bearer Token!", "color: #10b981; font-weight: bold; font-size: 13px;");
        }
      }

      // Handle Logout auto-unauthorize
      if (response.url && response.url.includes("/logout") && uiInitialized()) {
        ui.authActions.logout(["BearerAuth"]);
        console.log("%c[Swagger UI] Auto-Logged Out!", "color: #ef4444; font-weight: bold; font-size: 13px;");
      }
    }
  } catch (err) {
    console.warn("[Swagger UI] Auto auth error:", err);
  }

  return response;
};

const injectAuthCredentials = (request) => {
  let authorized;
  if (uiInitialized()) {
    const state = ui.getState().get("auth").get("authorized");
    if (state !== undefined && Object.keys(state.toJS()).length !== 0) {
      authorized = state.toJS();
    }
  } else if (![undefined, "{}"].includes(localStorage.authorized)) {
    authorized = JSON.parse(localStorage.authorized);
  }
  if (authorized === undefined) {
    return;
  }
  for (const authName of schemaAuthNames) {
    const authDef = authorized[authName];
    if (authDef === undefined || authDef.schema === undefined) {
      continue;
    }
    if (authDef.schema.type === "http" && authDef.schema.scheme === "bearer") {
      request.headers["Authorization"] = "Bearer " + authDef.value;
      return;
    } else if (authDef.schema.type === "http" && authDef.schema.scheme === "basic") {
      request.headers["Authorization"] = "Basic " + btoa(authDef.value.username + ":" + authDef.value.password);
      return;
    } else if (authDef.schema.type === "apiKey" && authDef.schema.in === "header") {
      request.headers[authDef.schema.name] = authDef.value;
      return;
    } else if (authDef.schema.type === "oauth2" && authDef.token.token_type === "Bearer") {
      request.headers["Authorization"] = `Bearer ${authDef.token.access_token}`;
      return;
    }
  }
};

const requestInterceptor = (request, ...args) => {
  if (request.loadSpec && schemaAuthNames.length > 0 && !schemaAuthFailed) {
    try {
      injectAuthCredentials(request);
    } catch (e) {
      console.error("schema auth injection failed with error: ", e);
    }
  }
  // selectively omit adding headers to mitigate CORS issues.
  if (!["GET", undefined].includes(request.method) && request.credentials === "same-origin") {
    request.headers["{{ csrf_header_name }}"] = "{{ csrf_token }}";
  }
  return request;
};

const ui = SwaggerUIBundle({
  url: "{{ schema_url|escapejs }}",
  dom_id: "#swagger-ui",
  presets: [SwaggerUIBundle.presets.apis],
  plugins,
  layout: "BaseLayout",
  requestInterceptor,
  responseInterceptor,
  ...swaggerSettings,
});

{% if oauth2_config %}ui.initOAuth({{ oauth2_config|safe }});{% endif %}
