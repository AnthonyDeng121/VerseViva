def is_gemini_location_unsupported(exc: Exception) -> bool:
    message = str(exc).lower()
    return "failed_precondition" in message and (
        "user location is not supported" in message
        or "location is not supported for the api use" in message
    )


def public_model_failure_message(exc: Exception) -> str:
    if is_gemini_location_unsupported(exc):
        return (
            "当前服务器所在区域暂不支持 Gemini 分析。"
            "录音仍可保存、回放和混音，本次不会计入练唱记忆。"
        )
    return "分析服务暂时不可用，请稍后重试。"
