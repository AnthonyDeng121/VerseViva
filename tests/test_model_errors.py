from server.services.model_errors import (
    is_gemini_location_unsupported,
    public_model_failure_message,
)


def test_gemini_location_error_is_sanitized_for_users() -> None:
    error = RuntimeError(
        "400 FAILED_PRECONDITION. {'error': {'message': "
        "'User location is not supported for the API use.'}}"
    )

    assert is_gemini_location_unsupported(error) is True
    message = public_model_failure_message(error)
    assert "当前服务器所在区域" in message
    assert "FAILED_PRECONDITION" not in message
    assert "User location" not in message


def test_other_model_errors_use_generic_public_message() -> None:
    message = public_model_failure_message(RuntimeError("secret provider detail"))

    assert message == "分析服务暂时不可用，请稍后重试。"
    assert "secret provider detail" not in message
