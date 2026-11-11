/// <reference types="cypress" />
describe('Login', () => {
  beforeEach(() => {
    cy.visit('/login');
  });

  it('logs in with valid credentials', () => {
    cy.get('[data-cy=email]').type('user@example.com');
    cy.get('[data-cy=password]').type('s3cret');
    cy.get('[data-cy=submit]').click();
    cy.url().should('include', '/dashboard');
    cy.contains('Welcome back').should('be.visible');
  });

  it('shows an error on a bad password', () => {
    cy.get('[data-cy=email]').type('user@example.com');
    cy.get('[data-cy=password]').type('wrong');
    cy.get('[data-cy=submit]').click();
    cy.get('.error').should('have.text', 'Invalid credentials');
    cy.wait(500);
  });

  it('loads the profile from an intercepted API', () => {
    cy.intercept('GET', '/api/profile', { fixture: 'profile.json' }).as('profile');
    cy.visit('/profile');
    cy.wait('@profile');
    cy.get('[data-cy=name]')
      .should('contain', 'Ada');
  });
});
