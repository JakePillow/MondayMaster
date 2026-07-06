from app.privacy.outbound import build_technical_analysis_payload, validate_outbound_payload


class OpenAIClient:
    """External transmission is disabled; only allowlisted payloads can be prepared."""

    prepare_payload = staticmethod(build_technical_analysis_payload)
    validate_payload = staticmethod(validate_outbound_payload)

    def send(self, *_args, **_kwargs):
        raise RuntimeError("External AI transmission is disabled in Phase 1.")
