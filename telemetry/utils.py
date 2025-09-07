class SafeDataTypeConverter:
    @staticmethod
    def safe_int(value, default=0):
        """
        安全轉換為整數

        Args:
            value: 要轉換的值
            default: 預設值

        Returns:
            轉換後的整數值
        """
        try:
            return int(value) if value is not None and str(value).strip() else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def safe_bool(value, default=False):
        """
        安全轉換為布林值

        Args:
            value: 要轉換的值
            default: 預設值

        Returns:
            轉換後的布林值
        """
        try:
            return (
                bool(SafeDataTypeConverter.safe_int(value))
                if value is not None
                else default
            )
        except (ValueError, TypeError):
            return default

    @staticmethod
    def safe_string(value, default=''):
        """
        安全轉換為字串

        Args:
            value: 要轉換的值
            default: 預設值

        Returns:
            轉換後的字串值
        """
        try:
            return str(value) if value is not None else default
        except (ValueError, TypeError):
            return default
