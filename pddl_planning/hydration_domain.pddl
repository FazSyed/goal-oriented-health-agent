(define (domain care_agent)
    (:requirements :strips :typing :negative-preconditions :disjunctive-preconditions :conditional-effects)

    (:types
        patient
    )

    ;; Conditions or states we care about
    (:predicates
        (hydrated ?p - patient) ; Patient is well-hydrated
        (dehydrated ?p - patient) ; Patient is mildly dehydrated
        (moderately_dehydrated ?p - patient) ; Moderate dehydration
        (severely_dehydrated ?p - patient) ; Severe dehydration
        (threshold_met ?p - patient) ; Goal: hydration is OK
        (checked ?p - patient) ; Indicates if hydration was checked
        (monitoring_active ?p - patient) ; Monitoring is active
    )

    ;; Action: Check the patient's hydration level
    (:action check_hydration
        :parameters (?p - patient)
        :precondition (and
            (monitoring_active ?p)
            (not (checked ?p))
        )
        :effect (and
            (checked ?p)
            ;; Determine if threshold is met based on current hydration state
            (when
                (hydrated ?p)
                (threshold_met ?p))
            (when
                (dehydrated ?p)
                (not (threshold_met ?p)))
            (when
                (moderately_dehydrated ?p)
                (not (threshold_met ?p)))
            (when
                (severely_dehydrated ?p)
                (not (threshold_met ?p)))
        )
    )

    ;; Action: Remind the patient to drink water (for mild dehydration)
    (:action remind
        :parameters (?p - patient)
        :precondition (and
            (checked ?p)
            (dehydrated ?p)
            (not (threshold_met ?p))
        )
        :effect (and
            (not (dehydrated ?p))
            (hydrated ?p)
            (threshold_met ?p)
        )
    )

    ;; Action: Alert the caregiver for moderate dehydration
    (:action alert_caregiver_moderate
        :parameters (?p - patient)
        :precondition (and
            (checked ?p)
            (moderately_dehydrated ?p)
            (not (threshold_met ?p))
        )
        :effect (and
            (not (moderately_dehydrated ?p))
            (hydrated ?p)
            (threshold_met ?p)
        )
    )

    ;; Action: Emergency alert for severe dehydration
    (:action alert_caregiver_severe
        :parameters (?p - patient)
        :precondition (and
            (checked ?p)
            (severely_dehydrated ?p)
            (not (threshold_met ?p))
        )
        :effect (and
            (not (severely_dehydrated ?p))
            (hydrated ?p)
            (threshold_met ?p)
        )
    )

    ;; Action: Recheck hydration after some time
    (:action recheck
        :parameters (?p - patient)
        :precondition (and
            (checked ?p)
            (not (threshold_met ?p))
        )
        :effect (and
            (not (checked ?p))
            (when
                (dehydrated ?p)
                (and
                    (not (dehydrated ?p))
                    (moderately_dehydrated ?p)))
        )
    )
)