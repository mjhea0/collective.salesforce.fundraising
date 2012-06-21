from five import grok
from zope import schema
from zope.interface import alsoProvides
from zope.component import getUtility
from zope.app.content.interfaces import IContentType
from Products.CMFCore.utils import getToolByName
from plone.directives import dexterity, form
from dexterity.membrane.content.member import IMember
from zope.app.container.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent
from collective.salesforce.content.interfaces import IModifiedViaSalesforceSync

from plone.namedfile.interfaces import IImageScaleTraversable

# Interface class; used to define content-type schema.

class IPerson(form.Schema, IImageScaleTraversable, IMember):
    """
    A person who is a user in Plone and a Contact in Salesforce
    """

    form.model("models/person.xml")

alsoProvides(IPerson, IContentType)

class Person(dexterity.Item):
    grok.implements(IPerson)

    def upsertToSalesforce(self):
        sfbc = getToolByName(self, 'portal_salesforcebaseconnector')
        
        res = sfbc.upsert('Email', {
            'type': 'Contact',
            'FirstName': self.first_name,
            'LastName': self.last_name,
            'Email': self.email,
            'HomePhone': self.phone,
            'MailingStreet': self.address,
            'MailingCity': self.city,
            'MailingState': self.state,
            'MailingPostalCode': self.zip,
            'MailingCountry': self.country,
            'Gender__c': self.gender,
            'Online_Fundraising_User__c' : True,
        })
        if not res[0]['success']:
            raise Exception(res[0]['errors'][0]['message'])

        # store the contact's Salesforce Id if it doesn't already have one
        if not getattr(self, 'sf_object_id', None):
            self.sf_object_id = res[0]['id']
    
        self.reindexObject()

        return res


@grok.subscribe(IPerson, IObjectAddedEvent)
def setOwnerRole(person, event):
    roles = list(person.get_local_roles_for_userid(person.email))

    if IModifiedViaSalesforceSync.providedBy(event):
        return

    if 'Owner' not in roles:
        roles.append('Owner')
        person.manage_setLocalRoles(person.email, roles)


@grok.subscribe(IPerson, IObjectAddedEvent)
def upsertNewSalesforceContact(person, event):
    # abort if this site doesn't have this product installed
    mdata = getToolByName(person, 'portal_memberdata')
    if 'sf_object_id' not in mdata.propertyIds():
        return

    # NOTE: commented out because we always want to update SF when a contact is updated
    # Skip if the sf_object_id is already set (could happen from 
    # collective.salesforce.content sync)
    #if getattr(person, 'sf_object_id', None):
    #    return

    # upsert Contact in Salesforce
    person.upsertToSalesforce()


@grok.subscribe(IPerson, IObjectModifiedEvent)
def upsertModifiedSalesforceContact(person, event):
    # abort if this site doesn't have this product installed
    mdata = getToolByName(person, 'portal_memberdata')
    if 'sf_object_id' not in mdata.propertyIds():
        return

    # upsert Contact in Salesforce
    person.upsertToSalesforce()
