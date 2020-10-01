Feature: Testing Trade Remedies user/organisation/role security model
  As a ...
  I want to ...
  So that I can ...

  Scenario: 1. Owner can add User to own organisation
    Given I am a public user "fred@test.com"
      And I am owner of the organisation "Org A"
      And there is a public user "sue@test.com"
     When I invite "sue@test.com" to "Org A"
     Then "sue@test.com" is a user of "Org A"
      And I am owner of the organisation "Org A"
      But "sue@test.com" is not owner of "Org A"

  Scenario: 2. Owner can make User owner of own organisation
    Given I am a public user "fred@test.com"
      And I am owner of the organisation "Org A"
      And there is a public user "sue@test.com"
     When I invite "sue@test.com" to "Org A"
      And I make "sue@test.com" owner of "Org A"
     Then "sue@test.com" is a user of "Org A"
      And I am owner of the organisation "Org A"
      And "sue@test.com" is owner of "Org A"

  Scenario: 3. User can not make User owner of own organisation
    Given I am a public user "fred@test.com"
      And I am not owner of the organisation "Org A"
      And there is a public user "sue@test.com"
     When I invite "sue@test.com" to "Org A"
      And I make "sue@test.com" owner of "Org A"  # this should fail -- how do we test for this?
     Then "sue@test.com" is a user of "Org A"
      And I am not owner of the organisation "Org A"
      But "sue@test.com" is not owner of the organisation "Org A"


"""        
      And I give "sue@test.com" access to case "Case X"
Scenario    2   Owner can add Owner to own organisation
    Given   I am a TRA user Owner
    When    I create a new Owner member to my Organisation account
    Then    they are able to add access the Owner tools for my organisation
    And they can access all cases relating to my organisation
    But they are unable to view cases belonging to other organisations
        
Scenario    3   Owner can add user to Case own organisation
    Given   I am a TRA user Owner
    When    my organisation has a role in a case
    Then    I can give case access to users within  my organisation
    And they are able to access that case for the appropriate actions
    But they cannot access cases to which they have not been assigned
"""        
