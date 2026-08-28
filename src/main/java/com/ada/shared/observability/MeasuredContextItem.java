package com.ada.shared.observability;

import java.lang.annotation.*;
@Target(ElementType.TYPE) @Retention(RetentionPolicy.RUNTIME) public @interface MeasuredContextItem { String value(); }
