(define (problem care_routine)
    (:domain care_agent)

    (:objects
        patient1 - patient
    )

    (:init
        (mildly_dehydrated patient1)
        (monitoring_active patient1)
    )

    (:goal
        (threshold_met patient1)
    )
)