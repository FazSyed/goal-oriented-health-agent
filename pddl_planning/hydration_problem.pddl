
(define (problem care_routine)
    (:domain care_agent)

    (:objects
        patient1 - patient
    )

    (:init
        (mildly_dehydrated patient1)
        (monitoring_active patient1)
        (oral_intake_feasible patient1)
    )

    (:goal
        (and
            (threshold_met patient1)
            (status_logged patient1)
        )
    )
)
