(define (problem care_routine)
    (:domain care_agent)

    (:objects
        patient1 - patient
    )

    (:init
        ;; Set the initial health condition
        (dehydrated patient1) ; Patient starts mildly dehydrated
        (monitoring_active patient1) ; Monitoring is active
        ;; Note: (checked patient1) is false initially, (threshold_met patient1) is false initially
    )

    (:goal
        ;; Goal: to bring hydration to safe level
        (threshold_met patient1)
    )
)