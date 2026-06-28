;; PDDL Problem definition for the hydration care routine

;; ================ Paste Test Case Below ================

;; Severe Dehydration Problem Case
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
        )
    )
)
;; ================ Test Case End ========================