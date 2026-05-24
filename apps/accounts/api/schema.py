from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BearerJWTScheme(OpenApiAuthenticationExtension):
    target_class = "rest_framework_simplejwt.authentication.JWTAuthentication"
    name = "bearerAuth"
    priority = 1  # override drf-spectacular's built-in jwtAuth (priority 0) cleanly

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
