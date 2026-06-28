(define (domain care_agent)
    (:requirements 
        :strips 
        :typing
        :negative-preconditions 
        :disjunctive-preconditions 
        :conditional-effects
    )

    (:types
        patient
    )

    ;; Conditions or states we care about
    (:predicates
        (euhydrated ?p - patient) ; Patient is well-hydrated
        (mildly_dehydrated ?p - patient) ; Patient is mildly dehydrated
        (moderately_dehydrated ?p - patient) ; Patient is moderately dehydrated
        (severely_dehydrated ?p - patient) ; Patient is severely dehydrated

        (oral_intake_feasible ?p - patient) ; Patient can take oral fluids

        (checked ?p - patient) ; Indicates if hydration was checked
        (ORS_consumed ?p - patient) ; Indicates if Oral Rehydration Solution was consumed
        (intake_monitored ?p - patient) ; Indicates if intake was monitored
        (hydration_rechecked ?p - patient) ; Indicates if hydration was rechecked
        (caregiver_alerted ?p - patient) ; Indicates if caregiver was alerted
        (transferred_to_hospital ?p - patient) ; Indicates if patient was transferred to hospital
        (fluids_administered ?p - patient) ; Indicates if fluids were administered
        (labs_rechecked ?p - patient) ; Indicates if labs were rechecked
        (vitals_monitored ?p - patient) ; Indicates if vitals were monitored
        (emergency_called ?p - patient) ; Indicates if emergency services were called

        (escalated_to_moderate ?p - patient) ; Indicates if care was escalated to moderate dehydration
        (escalated_to_severe ?p - patient) ; Indicates if care was escalated to severe dehydration

        (monitoring_active ?p - patient) ; Monitoring is active

        (threshold_met ?p - patient) ; Goal: hydration is OK

        (status_logged ?p - patient) ; Indicates if hydration status was logged
        
    )

    ;; Check the patient's hydration level
    (:action check_hydration
        :parameters (?p - patient)
        :precondition (and
            (monitoring_active ?p)
            (not (checked ?p))
        )
        :effect (and
            (checked ?p)
        )
    )


    ;; EUHYDRATION

    ;; log_status_euhydrated

    ;; No intervention needed, log and confirm euhydration
    (:action log_status_euhydrated
        :parameters (?p - patient)
        :precondition (and 
            (checked ?p)
            (euhydrated ?p)
            (not (fluids_administered ?p))
            (not (ORS_consumed ?p))
            (not (status_logged ?p))
        )
        :effect (and 
            (status_logged ?p)
            (threshold_met ?p)
        )
    )
    
    ;; MILD DEHYDRATION

    ;; consume_ORS → monitor_intake → recheck_hydration → log_status_mild

    (:action consume_ORS
        :parameters (?p - patient)
        :precondition (and 
            (checked ?p)
            (mildly_dehydrated ?p)
            (oral_intake_feasible ?p)
            (not (ORS_consumed ?p))
        )
        :effect (and 
            (ORS_consumed ?p)
        )
    )

    (:action monitor_intake
        :parameters (?p - patient)
        :precondition (and 
            (ORS_consumed ?p)
            (not (intake_monitored ?p))
        )
        :effect (and 
            (intake_monitored ?p)
        )
    )
    
    
    (:action recheck_hydration
        :parameters (?p - patient)
        :precondition (and 
            (intake_monitored ?p)
            (not (hydration_rechecked ?p))
        )
        :effect (and 
            (hydration_rechecked ?p)
            (not (mildly_dehydrated ?p))
            (euhydrated ?p)
            (threshold_met ?p)
        )
    )

    (:action log_status_mild
        :parameters (?p - patient)
        :precondition (and 
            (hydration_rechecked ?p)
            (threshold_met ?p)
            (not (status_logged ?p))
        )
        :effect (and 
            (status_logged ?p)
        )
    )
    
    ;; MILD --> MODERATE DEHYDRATION

    ;; escalate_to_moderate → alert_caregiver → transfer_to_hospital → administer_fluids_moderate → recheck_labs_moderate → monitor_vitals_moderate → log_status_moderate
    
    (:action escalate_to_moderate
        :parameters (?p - patient)
        :precondition (and 
            (checked ?p)
            (mildly_dehydrated ?p)
            (not (oral_intake_feasible ?p))
            (not (escalated_to_moderate ?p))
        )
        :effect (and 
            (escalated_to_moderate ?p)
            (not (mildly_dehydrated ?p))
            (moderately_dehydrated ?p)
        )
    )
    
    ;; MODERATE DEHYDRATION

    ;; alert_caregiver → transfer_to_hospital → administer_fluids_moderate → recheck_labs_moderate → monitor_vitals_moderate → log_status_moderate

    (:action alert_caregiver
        :parameters (?p - patient)
        :precondition (and
            (checked ?p)
            (moderately_dehydrated ?p)
            (not (caregiver_alerted ?p))
        )
        :effect (and
            (caregiver_alerted ?p)
        )
    )

    (:action transfer_to_hospital_moderate
        :parameters (?p - patient)
        :precondition (and 
            (caregiver_alerted ?p)
            (moderately_dehydrated ?p)
            (not (transferred_to_hospital ?p))
        )
        :effect (and 
            (transferred_to_hospital ?p)
        )
    )
    
    (:action administer_fluids_moderate
        :parameters (?p - patient)
        :precondition (and 
            (transferred_to_hospital ?p)
            (moderately_dehydrated ?p)
            (not (fluids_administered ?p))
        )
        :effect (and 
            (fluids_administered ?p)
        )
    )

    (:action recheck_labs_moderate
        :parameters (?p - patient)
        :precondition (and
            (fluids_administered ?p)
            (moderately_dehydrated ?p)
            (not (labs_rechecked ?p))
        )
        :effect (and
            (labs_rechecked ?p)
        )
    )
    
    (:action monitor_vitals_moderate
        :parameters (?p - patient)
        :precondition (and
            (labs_rechecked ?p)
            (moderately_dehydrated ?p)
            (not (vitals_monitored ?p))
        )
        :effect (and
            (vitals_monitored ?p)
            (not (moderately_dehydrated ?p))
            (euhydrated ?p)
            (threshold_met ?p)
        )
    )

    (:action log_status_moderate
        :parameters (?p - patient)
        :precondition (and
            (vitals_monitored ?p)
            (caregiver_alerted ?p)
            (not (emergency_called ?p))
            (transferred_to_hospital ?p)
            (threshold_met ?p)
            (not (status_logged ?p))
        )
        :effect (and
            (status_logged ?p)
        )
    )

    ;; MODERATE --> SEVERE DEHYDRATION

    ;;  escalate_to_severe → call_emergency → transfer_to_hospital → administer_fluids_severe → recheck_labs_severe → monitor_vitals_continuous → log_status_severe

    (:action escalate_to_severe
        :parameters (?p - patient)
        :precondition (and
            (labs_rechecked ?p)
            (moderately_dehydrated ?p)
            (not (escalated_to_severe ?p))
            (not (vitals_monitored ?p))
        )
        :effect (and
            (escalated_to_severe ?p)
            (not (moderately_dehydrated ?p))
            (severely_dehydrated ?p)
        )
    )

    ;; SEVERE DEHYDRATION

    ;; call_emergency → transfer_to_hospital → administer_fluids_severe → recheck_labs_severe → monitor_vitals_continuous → log_status_severe


    (:action call_emergency
        :parameters (?p - patient)
        :precondition (and
            (checked ?p)
            (severely_dehydrated ?p)
            (not (emergency_called ?p))
        )
        :effect (and
            (emergency_called ?p)
        )
    )

    (:action transfer_to_hospital_severe
        :parameters (?p - patient)
        :precondition (and 
            (emergency_called ?p)
            (severely_dehydrated ?p)
            (not (transferred_to_hospital ?p))
        )
        :effect (and 
            (transferred_to_hospital ?p)
        )
    )
    
    (:action administer_fluids_severe
        :parameters (?p - patient)
        :precondition (and 
            (transferred_to_hospital ?p)
            (severely_dehydrated ?p)
            (not (fluids_administered ?p))
        )
        :effect (and 
            (fluids_administered ?p)
        )
    )

    (:action recheck_labs_severe
        :parameters (?p - patient)
        :precondition (and
            (fluids_administered ?p)
            (severely_dehydrated ?p)
            (not (labs_rechecked ?p))
        )
        :effect (and
            (labs_rechecked ?p)
        )
    )
    
    (:action monitor_vitals_continuous
        :parameters (?p - patient)
        :precondition (and
            (labs_rechecked ?p)
            (severely_dehydrated ?p)
            (not (vitals_monitored ?p))
        )
        :effect (and
            (vitals_monitored ?p)
            (not (severely_dehydrated ?p))
            (euhydrated ?p)
            (threshold_met ?p)
        )
    )

    (:action log_status_severe
        :parameters (?p - patient)
        :precondition (and
            (vitals_monitored ?p)
            (transferred_to_hospital ?p)
            (emergency_called ?p)
            (threshold_met ?p)
            (not (status_logged ?p))
        )
        :effect (and
            (status_logged ?p)
        )
    )
)