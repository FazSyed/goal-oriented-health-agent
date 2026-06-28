
(define (problem care_routine)
    (:domain care_agent)

    (:objects
        patient1 - patient
    )

    (:init
        (severely_dehydrated patient1)
        (monitoring_active patient1)
    )

    (:goal
        (and
            (transferred_to_hospital patient1)
            (threshold_met patient1)
            (status_logged patient1)
        )
    )
)
